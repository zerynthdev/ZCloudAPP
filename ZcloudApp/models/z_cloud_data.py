# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, modules
from odoo.exceptions import UserError, ValidationError
import requests
import logging
from datetime import datetime
import base64

_logger = logging.getLogger(__name__)

"""
Classe per mostrare i dati ricevuti da Zcloud senza un collegamento ad un ordine di lavoro
"""


class ZcloudData(models.Model):
    _name = "z.cloud.data"
    _description = "The data recived from the device without a workorder"
    _inherit = ['mail.thread']
    _order = 'date_start, date_end'

    # archiviato o no
    active = fields.Boolean(
        string="Active",
        default=True,
        help="By unchecking the active field, you may hide a ZcloudData you will not use.",
        tracking=True
    )

    date_start = fields.Datetime(
        string="Date start",
        tracking=True
    )
    date_end = fields.Datetime(
        string="Date end",
        tracking=True
    )
    status = fields.Char(
        string="Status",
        tracking=True
    )
    electric_consume = fields.Float(
        string="Electric consume",
        tracking=True
    )
    workorder_not_found = fields.Char(
        string="Workorder not found",
        tracking=True
    )
    workorder_id = fields.Many2one(
        string="Workorder",
        comodel_name='mrp.workorder',
        tracking=True
    )
    zcloud_json_data = fields.Text(
        string="Json data",
        tracking=True
    )
    productivity_id = fields.Many2one(
        string="Productivity",
        comodel_name='mrp.workcenter.productivity',
        tracking=True
    )
    device_id = fields.Many2one(
        comodel_name="z.cloud.device",
        string="Device",
        tracking=True
    )
    is_working = fields.Boolean(
        string="Working",
        tracking=True,
        help="Define if is a working phase from Zerynth Cloud"
    )
    # pezzi prodotti
    pcs_ok = fields.Float(
        string="Pieces done",
        tracking=True
    )
    # pezzi scartati
    pcs_ko = fields.Float(
        string="Pieces discarded",
        tracking=True
    )
    # durata
    duration = fields.Float(
        string="Duration",
        compute="_compute_duration",
        store=True,
        tracking=True
    )

    @api.depends('date_end', 'date_start')
    def _compute_duration(self):
        for record in self:
            custom_duration = 0.0
            custom_duration = max(
                custom_duration, (record.date_end - record.date_start).total_seconds() / 60.0)
            record.duration = custom_duration

    def action_open_wizard(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "ZcloudApp.z_cloud_data_action_form")
        action['res_id'] = self.id
        return action

    def unlink(self):
        for record in self:
            if record.productivity_id:
                record.productivity_id.unlink()
        return super(ZcloudData, self).unlink()

    @api.constrains('workorder_id')
    def create_workorder_time_id(self):
        for record in self:
            if record.productivity_id:
                record.productivity_id.unlink()
            if record.date_start and record.date_end:
                # se c'è il workorder lo creo
                if record.workorder_id:
                    if not record.workorder_id.time_ids.filtered(lambda t: t.date_start == record.date_start and t.date_end == record.date_end):
                        if record.status:
                            loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                                [('name', '=', record.status), ('is_working', '=', record.is_working)], limit=1)
                            if not len(loss_id):
                                loss_id = self.env['mrp.workcenter.productivity.loss'].sudo().create({
                                    'name': record.status,
                                    'is_working': record.is_working
                                })
                        else:
                            # se non mi passa la fase metto quella produzione di odoo come default
                            loss_id = self.env['mrp.workcenter.productivity.loss'].search(
                                [('loss_id.loss_type', '=', 'productive')], limit=1)
                            if not len(loss_id):
                                raise UserError(
                                    _("You need to define at least one productivity loss in the category 'Productive'. Create one from the Manufacturing app, menu: Configuration / Productivity Losses."))
                        time_id_attr = {
                            "workorder_id": record.workorder_id.id,
                            "workcenter_id": record.workorder_id.workcenter_id.id,
                            "loss_id": loss_id.id,
                            "date_start": record.date_start,
                            "date_end": record.date_end,
                            "electric_consume": record.electric_consume,
                            "from_zcloud": True,
                            "pcs_ok": record.pcs_ok,
                            "pcs_ko": record.pcs_ko
                        }
                        productivity_id = self.env["mrp.workcenter.productivity"].create(
                            time_id_attr)
                        # ricalcolo la durata perchè non si ricalcola da sola BOH
                        custom_duration = 0.0
                        custom_duration = max(
                            custom_duration, (productivity_id.date_end - productivity_id.date_start).total_seconds() / 60.0)
                        productivity_id.duration = custom_duration
                        record.productivity_id = productivity_id.id
                        record.active = False
                    else:
                        raise UserError(
                            _("There is already a time track with the same start and end time in the work order %s" % record.workorder_id.display_name))
