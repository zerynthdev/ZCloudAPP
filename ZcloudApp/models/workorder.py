# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil import parser
import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    sequence_name = fields.Char(
        string="Name",
        copy=False
    )

    sequence = fields.Integer(
        string="Sequence",
        copy=False
    )

    reliability = fields.Float(
        string="Reliability",
        copy=False
    )

    reason = fields.Text(
        string="Reason",
        copy=False
    )

    zcloud_sincronize = fields.Boolean(
        string="Order sincronized on zerynth cloud",
        copy=False
    )

    zcloud_id = fields.Char(
        string="Zerynth cloud ID",
        copy=False
    )

    zcloud_stop = fields.Boolean(
        string="Order stopped on zerynth cloud",
        copy=False
    )

    zcloud_get_data = fields.Boolean(
        string="Order data retrive from zerynth cloud",
        copy=False
    )

    zcloud_electric_consume = fields.Float(
        string="Electric consume",
        copy=False,
        compute='_compute_zcloud_electric_consume',
        store=True,
    )

    # part program
    part_program_type = fields.Selection(
        string="Part program",
        related="workcenter_id.part_program_type",
        store=True,
    )
    part_program_file = fields.Binary(
        string="File",
    )
    part_program_file_name = fields.Char(
        string="File name",
    )

    # creo un allegato
    @api.constrains('part_program_file', 'part_program_file_name')
    def add_attachment_to_workorder(self):
        for record in self:
            if record.part_program_file:
                # TODO: chiedere a Matteo
                # elimino i vecchi file part program collegati a questo record(per non sovraccaricare)
                old_part_program_files = self.env['ir.attachment'].sudo().search(
                    [('res_model', '=', 'mrp.workorder'), ('is_part_program', '=', True), ('res_id', '=', record.id)])
                old_part_program_files.unlink()
                attachment_attr = {
                    'name': record.part_program_file_name,
                    'type': 'binary',
                    'res_model': 'mrp.workorder',
                    'res_id': record.id,
                    'datas': record.part_program_file,
                    'is_part_program': True
                }
                self.env['ir.attachment'].sudo().create(attachment_attr)

    part_program_url = fields.Char(
        string="Url",
    )
    part_program_path = fields.Char(
        string="Path",
    )
    part_program_variable = fields.Many2one(
        string="Variable",
        comodel_name="part.program.variable",
        domain="[('workcenter_id', '=', workcenter_id)]",
        copy=False
    )
    part_program_json = fields.Text(
        string="Json",
    )
    # SONO COMPUTE DEI TRACCIAMENTI TEMPORALI
    # pezzi prodotti
    pcs_ok = fields.Float(
        string="Pieces done",
        compute="_compute_pcs_ok_pcs_ko",
        store=True
    )
    # pezzi scartati
    pcs_ko = fields.Float(
        string="Pieces discarded",
        compute="_compute_pcs_ok_pcs_ko",
        store=True
    )

    # compute con la somma dei pezzi prodotti nei singoli tracciamenti temporali
    @api.depends('time_ids', 'time_ids.pcs_ok', 'time_ids.pcs_ko')
    def _compute_pcs_ok_pcs_ko(self):
        for record in self:
            record.pcs_ok = sum(record.time_ids.mapped('pcs_ok'))
            record.pcs_ko = sum(record.time_ids.mapped('pcs_ko'))

    # TODO: OVERRIDE DEL COMPUTE DELLA DURATA REALE
    @api.depends('time_ids.duration', 'qty_produced', 'time_ids', 'time_ids.loss_id', 'time_ids.loss_id.is_working')
    def _compute_duration(self):
        for order in self:
            # filtro i time_ids per quelli che sono di tipo working
            order.duration = sum(order.time_ids.filtered(
                lambda time: time.loss_id.is_working).mapped('duration'))
            # rounding 2 because it is a time
            order.duration_unit = round(
                order.duration / max(order.qty_produced, 1), 2)
            if order.duration_expected:
                order.duration_percent = max(-2147483648, min(2147483647, 100 * (
                    order.duration_expected - order.duration) / order.duration_expected))
            else:
                order.duration_percent = 0

    def name_get(self):
        result = []
        for workorder in self:
            name = "%s - %s - %s" % (workorder.sequence_name,
                                     workorder.product_id.name,
                                     workorder.name)
            result.append((workorder.id, name))
        return result

    @api.depends('time_ids.electric_consume')
    def _compute_zcloud_electric_consume(self):
        for order in self:
            order.zcloud_electric_consume = sum(
                order.time_ids.mapped('electric_consume'))

    @api.model_create_multi
    def create(self, vals):
        workorders = super(MrpWorkorder, self).create(vals)
        for workorder in workorders:
            if workorder.production_id:
                next_seq = '%%0%sd' % 3 % workorder.production_id.workorder_seqcount
                seq_name = "%s/%s" % (workorder.production_id.name,
                                      next_seq)
                seq_name = seq_name.replace("/", "-")
                while self.search([("sequence_name", "=", seq_name)]):
                    workorder.production_id.workorder_seqcount += 1
                    next_seq = '%%0%sd' % 3 % workorder.production_id.workorder_seqcount
                    seq_name = "%s/%s" % (workorder.production_id.name,
                                          next_seq)
                    seq_name = seq_name.replace("/", "-")
                workorder.sequence = workorder.production_id.workorder_seqcount
                workorder.sequence_name = seq_name
        return workorders

    """
    Funzione da chiamare tramite JSONRPC da Zcloud:
    parametro in ingresso:
    1) workorder_name che corrisponde al sequence_name in odoo EXAMPLE: WH-MO-00004-009
    Controlli:
    1) nel workcenter del workorder trovato deve essere impostato automatic_close_zcloud
    parametri di ritorno:
    1) True se tutto ok
    2) "Impossible to close the workorder: %s. Check the workcenter configuration" % workorder_id.name se il workcenter del workorder non ha il booleano automatic_close_zcloud a True 
    3) "There isn't a workorder with the name %s in odoo" % workorder_name se non è stato trovato nessun ordine con quel nome
    4) "There are multiple workorder with the name %s" % workorder_name se in odoo ci sono più ordini con quel nome
    """
    @api.model
    def close_order_from_zcloud(self, workorder_name):
        _logger.info(
            _("Closing workorder from Zcloud with the name %s" % workorder_name))
        workorder_id = self.search([('sequence_name', '=', workorder_name)])
        if len(workorder_id) == 1:
            if workorder_id.workcenter_id.automatic_close_zcloud:
                workorder_id.with_context(
                    automatic_close_zcloud=True).button_finish()
                return True
            else:
                self.env['z.cloud.log'].sudo().log(
                    name="close_order_from_zcloud",
                    request="close_order_from_zcloud",
                    response=_(
                        "Impossible to close the workorder: %s. Check the workcenter configuration" % workorder_id.name)
                )
                return _("Impossible to close the workorder: %s. Check the workcenter configuration" % workorder_id.name)
        elif len(workorder_id) == 0:
            self.env['z.cloud.log'].sudo().log(
                name="close_order_from_zcloud",
                request="close_order_from_zcloud",
                response=_(
                    "There isn't a workorder with the name %s in odoo" % workorder_name)
            )
            return _("There isn't a workorder with the name %s in odoo" % workorder_name)
        else:
            self.env['z.cloud.log'].sudo().log(
                name="close_order_from_zcloud",
                request="close_order_from_zcloud",
                response=_(
                    "There are multiple workorder with the name %s in odoo" % workorder_name)
            )
            return _("There are multiple workorder with the name %s in odoo" % workorder_name)

    """
    Questa funzione controlla le configurazioni impostate nel centro di lavoro:
    1) se nel centro di lavoro è impostato: automatic_close_new_order
        faccio un controllo se c'è già un workorder attivo nel centro di lavoro e lo restituisco per aprire wizard di conferma
    2) se nel centro di lavoro è impostato: automatic_close_next_order
        faccio un controllo se c'è già un workorder attivo nel centro di lavoro per quella produzione e lo restituisco per aprire wizard di conferma
    """

    def check_zcloud_workcenter_configuration(self):
        for record in self:
            if record.workcenter_id:
                workorder_ids_list = False
                # 1) automatic_close_new_order
                if record.workcenter_id.automatic_close_new_order:
                    workorder_ids = self.search(
                        [('workcenter_id', '=', record.workcenter_id.id),
                         ('id', '!=', record.id),
                         ('state', '=', 'progress')
                         ])
                    if not workorder_ids_list:
                        workorder_ids_list = workorder_ids
                    else:
                        workorder_ids_list += workorder_ids
                # 2) automatic_close_next_order
                if record.production_id and record.sequence:
                    # prendo tutte le operazioni di quella produzione antecedenti a quella che avvio(sequence minore)
                    # e che hanno il workcenter con il booleano automatic_close_next_order impostato
                    domain = [('id', '!=', record.id),
                              ('state', '=', 'progress'),
                              ('production_id', '=', record.production_id.id),
                              ('sequence', '<', record.sequence),
                              ('workcenter_id.automatic_close_next_order', '=', True)
                              ]
                    if workorder_ids_list:
                        domain.append(('id', 'not in', workorder_ids_list.ids))
                    workorder_ids = self.search(domain)
                    if not workorder_ids_list:
                        workorder_ids_list = workorder_ids
                    else:
                        workorder_ids_list += workorder_ids
                return workorder_ids_list

    """
    Questa funzione controlla le configurazioni Zcloud per quanto riguarda il PART PROGRAM e crea un dizionario con i valori da passare a Zcloud:
    1) se il prodotto della produzione è generico(generic_product) ritorna i valori inseriti all'interno del workorder stesso
    2) se il prodotto della produzione non è generico allora prendo i dati dall'operazione(operation_id) BOM:
    Valori ritornati:
        DIZIONARIO PER IL PART PROGRAM COSÌ:
            -  CHIAVE: part_program_type VALORE: part_program_type ('file', 'path', 'variable', 'json')
            -  CHIAVE: part_program_data VALORE: part_program_(campo corrispondente al type)
    """

    def check_zcloud_part_program_configuration(self):
        self.ensure_one()
        is_workorder = False
        is_bom = False
        if self.production_id and self.production_id.product_id:
            if self.production_id.product_id.generic_product:
                is_workorder = True
                return is_workorder, is_bom, self.create_part_program_dict_from_workorder()
            else:
                if self.operation_id:
                    is_bom = True
                    return is_workorder, is_bom, self.operation_id.create_part_program_dict_from_routing()
        return is_workorder, is_bom, {}

    """
    FUNZIONE CHE RITORNA UN DIZIONARIO PER IL PART PROGRAM COSÌ:
        -  CHIAVE: part_program_type VALORE: part_program_type ('file', 'path', 'variable', 'json')
        -  CHIAVE: part_program_data VALORE: part_program_(campo corrispondente al type)
    """

    def create_part_program_dict_from_workorder(self):
        self.ensure_one()
        part_program_dict = {}
        if self.part_program_type == 'file':
            if self.part_program_file:
                # ricerco l'allegato
                attachment = self.env['ir.attachment'].sudo().search(
                    [('res_id', '=', self.id), ('res_model', '=', 'mrp.workorder'), ('name', '=', self.part_program_file_name)], limit=1)
                if attachment:
                    attachment.generate_access_token()
                    odoo_url = self.env['ir.config_parameter'].sudo(
                    ).get_param('web.base.url')
                    attachment_url = odoo_url + \
                        '/web/content?id={}&access_token={}'.format(
                            attachment.id, attachment.access_token)
                    part_program_dict['part_program_type'] = self.part_program_type
                    part_program_dict['part_program_data'] = attachment_url
            if self.part_program_url:
                part_program_dict['part_program_type'] = self.part_program_type
                part_program_dict['part_program_data'] = self.part_program_url
        if self.part_program_type == 'path':
            if self.part_program_path:
                part_program_dict['part_program_type'] = self.part_program_type
                part_program_dict['part_program_data'] = self.part_program_path
        if self.part_program_type == 'variable':
            if self.part_program_variable:
                part_program_dict['part_program_type'] = self.part_program_type
                part_program_dict['part_program_data'] = self.part_program_variable.name
        if self.part_program_type == 'json':
            if self.part_program_json:
                part_program_dict['part_program_type'] = self.part_program_type
                try:
                    json_data = eval(self.part_program_json)
                except Exception as error:
                    raise UserError(
                        _("There was an error reading the Json, please check the json in the workorder.\nError: %s" % error))
                part_program_dict['part_program_data'] = json_data
        return part_program_dict

    # avvio del workorder e quindi creazione e avvio su Zcloud
    def button_start(self):
        if not self.zcloud_sincronize:
            # il part program adesso viene controllato solo se c'è un device collegato al workcenter
            if self.workcenter_id and self.workcenter_id.device_id:
                is_workorder, is_bom, part_program_dict = self.check_zcloud_part_program_configuration()
                if not part_program_dict and self.part_program_type:
                    if is_workorder:
                        raise UserError(_("The work order %s don't have configured a part program but the part program type '%s' is set in the workcenter %s." % (
                            self.sequence_name, self.part_program_type, self.workcenter_id.name)))
                    if is_bom:
                        raise UserError(_("The operation(BOM:%s) %s don't have configured a part program but the part program type '%s' is set in the workcenter %s." % (
                            self.operation_id.bom_id.display_name, self.operation_id.name, self.part_program_type, self.workcenter_id.name)))
                # controllo delle configurazioni workcenter se ci sono da chiudere altri ordini di lavoro
                workorder_ids_in_progress = self.check_zcloud_workcenter_configuration()
                if workorder_ids_in_progress:
                    # se ci sono allora richiesta conferma di come comportarsi tramite wizard
                    if not self.env.context.get('wizard_continue_without_stop'):
                        if not self.env.context.get('wizard_start_confirm'):
                            # apro il wizard se non ho la conferma dello stop nel context
                            action = self.env['ir.actions.act_window']._for_xml_id(
                                'ZcloudApp.confirm_start_workorder_wizard_action')
                            wizard_text_html = "<span>Starting the work order <b>%s</b> will stop these work orders: <b>%s</b></span><br/><span>If this is an error check the workcenter <b>%s</b> Zcloud configuration<span>" % (
                                self.sequence_name, workorder_ids_in_progress.mapped('sequence_name'), self.workcenter_id.name)
                            action['context'] = {
                                'default_workorder_id': self.id, 'default_workorder_ids': workorder_ids_in_progress.ids, 'default_wizard_text_html': wizard_text_html}
                            return action
                        else:
                            # mi ha dato la conferma stoppo i workorder
                            for workorder in workorder_ids_in_progress:
                                workorder.with_context(
                                    automatic_close_new_order=True).button_finish()
            if self.workcenter_id and self.workcenter_id.device_id:
                zcloud_crete_start = self.workcenter_id.device_id.create_and_start_order(
                    self, part_program_dict)
                if self.production_id:
                    odoobot = self.env.ref('base.partner_root')
                    # sincronizzazione creazione riuscita
                    if zcloud_crete_start:
                        self.production_id.sudo().message_post(
                            body=_("<b>OK CREAZIONE:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' creato e avviato su Zcloud." %
                                   (self.sequence_name, self.name, self.workcenter_id.device_id.device_name, self.workcenter_id.name)),
                            message_type='comment',
                            subtype_id=self.env.ref(
                                'mail.mt_note').id,
                            subject=_(
                                "Creato ordine di lavoro su Zcloud"),
                            record_name=self.production_id.name,
                            author_id=odoobot.id)
                    # sincronizzazione creazione errata
                    else:
                        self.production_id.sudo().message_post(
                            body=_("<b>ERRORE CREAZIONE:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' non creato e avviato su Zcloud. <b>Controlla nei log</b>" %
                                   (self.sequence_name, self.name, self.workcenter_id.device_id.device_name, self.workcenter_id.name)),
                            message_type='comment',
                            subtype_id=self.env.ref(
                                'mail.mt_note').id,
                            subject=_(
                                "Errore creazione ordine di lavoro su Zcloud"),
                            record_name=self.production_id.name,
                            author_id=odoobot.id)
        return super().button_start()

    # completamento del workorder e quindi stop su Zcloud

    def button_finish(self):
        res = super().button_finish()
        for workorder in self:
            if workorder.workcenter_id and workorder.workcenter_id.device_id:
                zcloud_stop = workorder.workcenter_id.device_id.stop_order(
                    workorder)
                if workorder.production_id:
                    odoobot = self.env.ref('base.partner_root')
                    # creo una nota per dire che è stato chiuso automaticamente da odoo per la configurazione del workcenter
                    if self.env.context.get('automatic_close_new_order'):
                        workorder.production_id.sudo().message_post(
                            body=_("<b>OK STOP:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' fermato automaticamente come da configurazione del centro di lavoro." %
                                   (workorder.sequence_name, workorder.name, workorder.workcenter_id.device_id.device_name, workorder.workcenter_id.name)),
                            message_type='comment',
                            subtype_id=self.env.ref(
                                'mail.mt_note').id,
                            subject=_(
                                "Fermato ordine di lavoro automaticamente da odoo"),
                            record_name=workorder.production_id.name,
                            author_id=odoobot.id)
                        # ADESSO C'È IL POLLING DA ZCLOUD
                        # workorder.workcenter_id.device_id.get_order_data(
                        #     workorder)
                    # nota per chiusura da Zcloud automatic_close_zcloud in context
                    if self.env.context.get('automatic_close_zcloud'):
                        workorder.production_id.sudo().message_post(
                            body=_("<b>OK STOP:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' fermato da Zcloud." %
                                   (workorder.sequence_name, workorder.name, workorder.workcenter_id.device_id.device_name, workorder.workcenter_id.name)),
                            message_type='comment',
                            subtype_id=self.env.ref(
                                'mail.mt_note').id,
                            subject=_(
                                "Fermato ordine di lavoro da Zcloud"),
                            record_name=workorder.production_id.name,
                            author_id=odoobot.id)
                        # ADESSO C'È IL POLLING DA ZCLOUD
                        # workorder.workcenter_id.device_id.get_order_data(
                        #     workorder)
                    # sincronizzazione stop riuscita
                    if zcloud_stop:
                        workorder.production_id.sudo().message_post(
                            body=_("<b>OK STOP:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' fermato su Zcloud." %
                                   (workorder.sequence_name, workorder.name, workorder.workcenter_id.device_id.device_name, workorder.workcenter_id.name)),
                            message_type='comment',
                            subtype_id=self.env.ref(
                                'mail.mt_note').id,
                            subject=_(
                                "Fermato ordine di lavoro su Zcloud"),
                            record_name=workorder.production_id.name,
                            author_id=odoobot.id)
                        # ADESSO C'È IL POLLING DA ZCLOUD
                        # workorder.workcenter_id.device_id.get_order_data(
                        #     workorder)
                    # sincronizzazione stop errata
                    else:
                        workorder.production_id.sudo().message_post(
                            body=_("<b>ERRORE STOP:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' non fermato su Zcloud. <b>Controlla nei log</b>" %
                                   (workorder.sequence_name, workorder.name, workorder.workcenter_id.device_id.device_name, workorder.workcenter_id.name)),
                            message_type='comment',
                            subtype_id=self.env.ref(
                                'mail.mt_note').id,
                            subject=_(
                                "Errore fermare ordine di lavoro su Zcloud"),
                            record_name=workorder.production_id.name,
                            author_id=odoobot.id)
        return res

    # delete del workorder e quindi delete su Zcloud
    def unlink(self):
        for workorder in self:
            if workorder.zcloud_sincronize and not workorder.zcloud_stop:
                if workorder.workcenter_id and workorder.workcenter_id.device_id:
                    zcloud_delete = workorder.workcenter_id.device_id.delete_order(
                        workorder)
                    # sincronizzazione delete riuscita
                    if workorder.production_id:
                        odoobot = self.env.ref('base.partner_root')
                        if zcloud_delete:
                            workorder.production_id.sudo().message_post(
                                body=_("<b>OK ELIMINAZIONE:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' eliminato su Zcloud." %
                                       (workorder.sequence_name, workorder.name, workorder.workcenter_id.device_id.device_name, workorder.workcenter_id.name)),
                                message_type='comment',
                                subtype_id=self.env.ref(
                                    'mail.mt_note').id,
                                subject=_(
                                    "Eliminato ordine di lavoro su Zcloud"),
                                record_name=workorder.production_id.name,
                                author_id=odoobot.id)
                        # sincronizzazione delete errata
                        else:
                            workorder.production_id.sudo().message_post(
                                body=_("<b>ERRORE ELIMINAZIONE:</b> ordine di lavoro '%s', operazione '%s', collegato al device '%s' del centro di lavoro '%s' non eliminato su Zcloud. <b>Controlla nei log</b>" %
                                       (workorder.sequence_name, workorder.name, workorder.workcenter_id.device_id.device_name, workorder.workcenter_id.name)),
                                message_type='comment',
                                subtype_id=self.env.ref(
                                    'mail.mt_note').id,
                                subject=_(
                                    "Errore eliminare ordine di lavoro su Zcloud"),
                                record_name=workorder.production_id.name,
                                author_id=odoobot.id)
        return super(MrpWorkorder, self).unlink()

    """
    Funzione che processa i dati ricevuti da Zcloud tramite la chiamata get_order_data()
    ESEMPIO:
    [
        {
        "start_ts": "{start_ts}",
        "end_ts": "{end_ts}",
        "cons": "{cons}"
        },
        {
        "start_ts": "{start_ts}",
        "end_ts": "{end_ts}",
        "cons": "{cons}"
        },
        ecc. ecc.,
    ]
    # ADESSO I DATI SARANNO CREATI COME z.cloud.queue e saranno così
    {
        "datas": [
            {
                "start": "2023-07-24T15:35:52Z", DATA E ORA INIZIO
                "end": "2023-07-24T15:41:53Z", DATA E ORA FINE
                "cons": 166.962, CONSUMO ELETTRICO
                "pcs_ok": 7, PEZZI PRODOTTI OK
                "pcs_ko": 2, PEZZI SCARTATI KO
                "asset_id": "ast-8jdhbasjdhga", ASSET_ID
                "device_id": "dev-84qrsgjlmzwj", DEVICE_ID
                "order_id": "", NOME DELL'ORDINE DI LAVORO DI ODOO
                "status": "working" NOME DELLA FASE(DA CREARE SE NON C'È IN ODOO)
                "status_code": 0 (idle) 1 (working) DEFINISCE IL TIPO DI FASE DELLA MACCHINA
            }
        ]
    }
    Se Zcloud mi passa la fase 'status' allora la cerco tra quelle di odoo e la creo, in caso contrario
    imposto come fase quella della produzione di default di odoo: ('loss_type', '=', 'productive')
    """

    def process_zcloud_data_from_list(self, order_datas=[]):
        self.ensure_one()
        # rimuovo quelli non creati da Zcloud (from_zcloud == False)
        for time_id in self.time_ids.filtered(lambda t: t.from_zcloud == False):
            time_id.unlink()
        for order_data in order_datas:
            if "status" in order_data and order_data['status'] and "status_code" in order_data:
                loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                    [('name', '=', order_data['status']), ('is_working', '=', bool(order_data["status_code"]))], limit=1)
                if not loss_id:
                    loss_id = self.env['mrp.workcenter.productivity.loss'].sudo().create({
                        'name': order_data['status'],
                        'is_working': bool(order_data["status_code"])
                    })
            else:
                # se non mi passa la fase 'status' metto quella produzione di odoo come default
                loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                    [('loss_id.loss_type', '=', 'productive')], limit=1)
                if not len(loss_id):
                    raise UserError(
                        _("You need to define at least one productivity loss in the category 'Productive'. Create one from the Manufacturing app, menu: Configuration / Productivity Losses."))
            time_id_attr = {
                "workorder_id": self.id,
                "workcenter_id": self.workcenter_id.id,
                "loss_id": loss_id.id,
                "from_zcloud": True,
            }
            if "start" in order_data:
                time_id_attr["date_start"] = parser.parse(
                    order_data["start"]).strftime("%Y-%m-%d %H:%M:%S")
            if "end" in order_data:
                time_id_attr["date_end"] = parser.parse(
                    order_data["end"]).strftime("%Y-%m-%d %H:%M:%S")
            if "cons" in order_data:
                time_id_attr["electric_consume"] = order_data["cons"]
            if "pcs_ok" in order_data:
                try:
                    pcs_ok = float(order_data["pcs_ok"])
                except:
                    pcs_ok = 0
                time_id_attr["pcs_ok"] = pcs_ok
            if "pcs_ko" in order_data:
                try:
                    pcs_ko = float(order_data["pcs_ko"])
                except:
                    pcs_ko = 0
                time_id_attr["pcs_ko"] = pcs_ko
            new_time_id = self.env["mrp.workcenter.productivity"].create(
                time_id_attr)
            custom_duration = 0.0
            custom_duration = max(
                custom_duration, (new_time_id.date_end - new_time_id.date_start).total_seconds() / 60.0)
            new_time_id.duration = custom_duration
        if self.workcenter_id.device_id:
            odoobot = self.env.ref('base.partner_root')
            self.workcenter_id.device_id.sudo().message_post(
                body=_("Scaricati i dati relativi all'ordine di lavoro '%s', operazione '%s' da Zcloud.<br/>Dati ricevuti da Zcloud:<br/>%s" %
                       (self.sequence_name, self.name, order_datas)),
                message_type='comment',
                subtype_id=self.env.ref(
                    'mail.mt_note').id,
                subject=_(
                    "Recupero dati ordine di lavoro da Zcloud"),
                record_name=self.workcenter_id.device_id.device_name,
                author_id=odoobot.id)
        # SE NE WORKCENTER C'È CALCOLA TEMPI DI IDLE(MACCHINA NON ATTIVA) ALLORA ODOO CREA I TEMPI DI INATTIVITÀ
        if self.workcenter_id.automatic_idle_time:
            self.create_zcloud_time_ids_stop()
        # CALCOLO ATTREZZAGGIO
        if self.workcenter_id.automatic_tooling_time:
            self.create_zcloud_time_ids_tooling_time()
        return True

    # QUESTA FUNZIONE CREA GLI INTERVALLI TRA UN PROCESSO DI ATTIVITÀ DI PRODUZIONE E L'ALTRO
    # i tempi tra un ciclo e l'altro portano la fase di 'Idle' o quella impostata nel workcenter
    def create_zcloud_time_ids_stop(self):
        self.ensure_one()
        if len(self.time_ids) > 1:
            loss_name = "Idle"
            if self.workcenter_id.idle_phase_name:
                loss_name = self.workcenter_id.idle_phase_name
            loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                [('name', '=', loss_name), ('is_working', '=', False)], limit=1)
            if not len(loss_id):
                loss_id = self.env['mrp.workcenter.productivity.loss'].sudo().create({
                    'name': loss_name,
                    'is_working': False
                })
            # ordino le righe per orario
            time_ids = self.time_ids.sorted(key=lambda x: x.date_start)
            for i in range(len(time_ids) - 1):
                time_id_attr = {
                    "workorder_id": self.id,
                    "workcenter_id": self.workcenter_id.id,
                    "loss_id": loss_id.id,
                    "date_start": time_ids[i].date_end + timedelta(seconds=1),
                    "date_end": time_ids[i + 1].date_start + timedelta(seconds=-1),
                    "from_zcloud": True
                }
                self.env["mrp.workcenter.productivity"].create(
                    time_id_attr)
        return True

    # QUESTA FUNZIONE CREA IL TEMPO DI ATTREZZAGGIO CALCOLATO COME DATA INIZIO DELL'ORDINE DI LAVORO E IL PRIMO CICLO
    @api.constrains('date_finished', 'time_ids')
    def create_zcloud_time_ids_tooling_time(self):
        for record in self:
            if record.workcenter_id and record.workcenter_id.automatic_tooling_time:
                if len(record.time_ids) > 0 and record.date_start:
                    loss_name = "Tooling"
                    if record.workcenter_id.tooling_phase_name:
                        loss_name = record.workcenter_id.tooling_phase_name
                    # controllo che non ci sia solo un tempo registrato e questo sia di Tooling
                    if len(record.time_ids) == 1 and record.time_ids[0].loss_id.name == loss_name:
                        record.time_ids[0].from_zcloud = True
                    else:
                        # elimino attrezzaggi già calcolati nel caso in cui i dati arrivano dopo
                        tooling_productivity_ids = record.time_ids.filtered(
                            lambda time: time.loss_id.name == loss_name)
                        tooling_productivity_ids.unlink()
                        loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                            [('name', '=', loss_name), ('is_working', '=', False)], limit=1)
                        if not len(loss_id):
                            loss_id = self.env['mrp.workcenter.productivity.loss'].sudo().create({
                                'name': loss_name,
                                'is_working': False
                            })
                        # filtro le righe cercando la prima con una fase is_working e poi le ordino per orario di inizio
                        time_ids = record.time_ids.sorted(
                            key=lambda x: x.date_start)
                        if time_ids:
                            if time_ids[0].loss_id.is_working:
                                if record.date_start < time_ids[0].date_start:
                                    time_id_attr = {
                                        "workorder_id": record.id,
                                        "workcenter_id": record.workcenter_id.id,
                                        "loss_id": loss_id.id,
                                        "date_start": record.date_start,
                                        "date_end": time_ids[0].date_start + timedelta(seconds=-1),
                                        "from_zcloud": True
                                    }
                                    new_time_id = self.env["mrp.workcenter.productivity"].create(
                                        time_id_attr)
                                    custom_duration = 0.0
                                    custom_duration = max(
                                        custom_duration, (new_time_id.date_end - new_time_id.date_start).total_seconds() / 60.0)
                                    new_time_id.duration = custom_duration
                            else:
                                if record.date_start < time_ids[0].date_start:
                                    time_ids[0].date_start = record.date_start
                                time_ids[0].loss_id = loss_id.id
        return True
