# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import uuid


class MrpWorkcenter(models.Model):
    _name = "mrp.workcenter"
    _inherit = ['mrp.workcenter', 'mail.thread']

    device_id = fields.Many2one(
        comodel_name="z.cloud.device",
        string="Device",
        domain="[('workcenter_id','=',False)]",
        tracking=True
    )
    # calcolo dell'attrezzaggio
    automatic_idle_time = fields.Boolean(
        string="Automatic idle time",
        copy=False,
        tracking=True,
        help="If checked Odoo will calculate the idle time based on the difference between the start and the next start of times of the workorder"
    )
    # nome per definire la fase tra una traccia temporale e l'altra
    idle_phase_name = fields.Char(
        string="Idle phase name",
        copy=False,
        tracking=True,
        default="Idle",
        help="The name of the idle phase. The time between each cicle"
    )

    zcloud_sincronize = fields.Boolean(
        string="Workcenter sincronized on zerynth cloud",
        copy=False,
        tracking=True
    )
    # calcolo dell'attrezzaggio
    automatic_tooling_time = fields.Boolean(
        string="Automatic tooling time",
        copy=False,
        tracking=True,
        help="If checked Odoo will calculate the tooling time based on the difference between the start of the workorder and the first data recived"
    )
    # nome per definire la fase di attrezzaggio
    tooling_phase_name = fields.Char(
        string="Tooling phase name",
        copy=False,
        tracking=True,
        default="Tooling",
        help="The name of the tooling phase"
    )

    # configurazioni
    automatic_close_zcloud = fields.Boolean(
        string="Automatic workorder close from Zerynth cloud(Authorization)",
        tracking=True,
        default=True,
        help="Zerynth cloud can close the workorder."
    )
    automatic_close_new_order = fields.Boolean(
        string="Automatic workorder close at the start of new order",
        tracking=True,
        default=True,
        help="A workorder will be close if a new one start on the workcenter."
    )
    automatic_close_next_order = fields.Boolean(
        string="Automatic workorder close if the next one on the single production start",
        tracking=True,
        default=True,
        help="A workorder will be close if the next one on the single production start."
    )
    # part program
    part_program_type = fields.Selection(
        selection=[
            ('file', 'File'),
            ('path', 'Path'),
            ('variable', 'Variable'),
            ('json', 'Json')
        ],
        string="Part program",
        default=False,  # FIX default false perchè non è detto che un workcenter debba essere collegato per forza ad un device
        tracking=True
    )
    # collegamento alle variabili
    part_progra_variable_ids = fields.One2many(
        string="Variables",
        comodel_name="part.program.variable",
        inverse_name="workcenter_id",
        tracking=True
    )
    # obbligatorietà delle variabili se il part program è di tipo 'variable'
    @api.constrains('part_program_type')
    def check_required_part_progra_variable_ids(self):
        for record in self:
            if record.part_program_type == 'variable':
                if not record.part_progra_variable_ids:
                    raise UserError(
                        _("Part program 'variable' has been set but no variables has been created for this workcenter"))
    # codice univoco da inviare a Zerynth Cloud per la sincronizzazione del centro
    workcenter_uuid = fields.Char(
        string="Uuid",
        tracking=True,
        help="Used to sincronyze with Zerynth Cloud"
    )

    @api.model_create_multi
    def create(self, vals):
        workcenters = super(MrpWorkcenter, self).create(vals)
        for workcenter in workcenters:
            if not workcenter.workcenter_uuid:
                workcenter.workcenter_uuid = str(uuid.uuid4())
        return workcenters

    @api.constrains("device_id")
    def unique_device_id_for_workcenter_costrains(self):
        for record in self:
            if record.device_id:
                if self.search([("id", "!=", record.id), ("device_id", "=", record.device_id.id)]):
                    raise ValidationError(
                        _("Il device selezionato è gia collegato ad un altro centro di lavoro"))
                record.device_id._compute_workcenter_id()
            else:
                record.zcloud_sincronize = False
                # reset del part program se non c'è il device
                record.part_program_type = False

    def button_create_connection_asset_workspace(self):
        for record in self:
            if record.device_id:
                zcloud_device_workcenter_connection = record.device_id.create_connection_asset_workspace(
                    record)
                odoobot = self.env.ref('base.partner_root')
                if zcloud_device_workcenter_connection:
                    record.device_id.sudo().message_post(
                        body=_("<b>OK:</b> Creata connesione tra il device e il workcenter '%s' su Zcloud" %
                               (record.name)),
                        message_type='comment',
                        subtype_id=self.env.ref(
                            'mail.mt_note').id,
                        subject=_(
                            "Creato connessione device-workcenter su Zcloud"),
                        record_name=record.device_id.device_name,
                        author_id=odoobot.id)
                    record.sudo().message_post(
                        body=_("<b>OK:</b> Creata connesione tra il device e il workcenter '%s' su Zcloud" %
                               (record.name)),
                        message_type='comment',
                        subtype_id=self.env.ref(
                            'mail.mt_note').id,
                        subject=_(
                            "Creato connessione device-workcenter su Zcloud"),
                        record_name=record.name,
                        author_id=odoobot.id)
                # sincronizzazione creazione errata
                else:
                    record.device_id.sudo().message_post(
                        body=_("<b>ERRORE:</b> Connessione tra il device e il workcenter '%s' fallita su Zcloud. <b>Controlla nei log</b>" %
                               (record.name)),
                        message_type='comment',
                        subtype_id=self.env.ref(
                            'mail.mt_note').id,
                        subject=_(
                            "Errore connessione device-workcenter su Zcloud"),
                        record_name=record.device_id.device_name,
                        author_id=odoobot.id)
                    record.sudo().message_post(
                        body=_("<b>ERRORE:</b> Connessione tra il device e il workcenter '%s' fallita su Zcloud. <b>Controlla nei log</b>" %
                               (record.name)),
                        message_type='comment',
                        subtype_id=self.env.ref(
                            'mail.mt_note').id,
                        subject=_(
                            "Errore connessione device-workcenter su Zcloud"),
                        record_name=record.name,
                        author_id=odoobot.id)
