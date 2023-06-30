# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    device_id = fields.Many2one(
        comodel_name="z.cloud.device",
        string="Device",
        domain="[('workcenter_id','=',False)]"
    )

    zcloud_sincronize = fields.Boolean(
        string="Workcenter sincronized on zerynth cloud",
        copy=False
    )

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
