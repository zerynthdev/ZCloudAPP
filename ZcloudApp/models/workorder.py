# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil import parser


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    sequence_name = fields.Char(
        string="Name",
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
                workorder.sequence_name = seq_name
        return workorders

    # avvio del workorder e quindi creazione e avvio su Zcloud
    def button_start(self):
        res = super().button_start()
        if self.workcenter_id and self.workcenter_id.device_id:
            zcloud_crete_start = self.workcenter_id.device_id.create_and_start_order(
                self)
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
        return res

    # completamento del workorder e quindi stop su Zcloud
    def button_finish(self):
        res = super().button_finish()
        for workorder in self:
            if workorder.workcenter_id and workorder.workcenter_id.device_id:
                zcloud_stop = workorder.workcenter_id.device_id.stop_order(
                    workorder)
                if workorder.production_id:
                    odoobot = self.env.ref('base.partner_root')
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
                        workorder.workcenter_id.device_id.get_order_data(
                            workorder)
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
    """

    def process_zcloud_data_from_list(self, order_datas=[]):
        self.ensure_one()
        self.time_ids = [(5, 0, 0)]
        for order_data in order_datas:
            loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                [('loss_type', '=', 'productive')], limit=1)
            if not len(loss_id):
                raise UserError(
                    _("You need to define at least one productivity loss in the category 'Productive'. Create one from the Manufacturing app, menu: Configuration / Productivity Losses."))
            time_id_attr = {
                "workorder_id": self.id,
                "workcenter_id": self.workcenter_id.id,
                "loss_id": loss_id.id
            }
            if "start" in order_data:
                time_id_attr["date_start"] = parser.parse(
                    order_data["start"]).strftime("%Y-%m-%d %H:%M:%S")
            if "end" in order_data:
                time_id_attr["date_end"] = parser.parse(
                    order_data["end"]).strftime("%Y-%m-%d %H:%M:%S")
            if "cons" in order_data:
                time_id_attr["electric_consume"] = order_data["cons"]
            self.env["mrp.workcenter.productivity"].create(
                time_id_attr)
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
        self.create_zcloud_time_ids_stop()
        return True

    # QUESTA FUNZIONE CREA GLI INTERVALLI TRA UN PROCESSO DI ATTIVITÀ DI PRODUZIONE E L'ALTRO
    def create_zcloud_time_ids_stop(self):
        self.ensure_one()
        if len(self.time_ids) > 1:
            loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                [('loss_type', '=', 'availability')], limit=1)
            if not len(loss_id):
                raise UserError(
                    _("You need to define at least one productivity loss in the category 'Performance'. Create one from the Manufacturing app, menu: Configuration / Productivity Losses."))
            # ordino le righe per orario
            time_ids = self.time_ids.sorted(key=lambda x: x.date_start)
            for i in range(len(time_ids) - 1):
                time_id_attr = {
                    "workorder_id": self.id,
                    "workcenter_id": self.workcenter_id.id,
                    "loss_id": loss_id.id,
                    "date_start": time_ids[i].date_end + timedelta(seconds=1),
                    "date_end": time_ids[i + 1].date_start + timedelta(seconds=-1)
                }
                self.env["mrp.workcenter.productivity"].create(
                    time_id_attr)
        return True
