# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ZcloudDeviceLine(models.Model):
    _name = "z.cloud.device.line"
    _description = "Lines with the values of the device"
    _rec_names_search = ['name', 'device_id.name']
    _order = 'timestamp_device desc'

    device_id = fields.Many2one(
        comodel_name="z.cloud.device",
        string="Device"
    )

    timestamp_device = fields.Datetime(
        string="Timestamp device",
    )

    timestamp_in = fields.Datetime(
        string="Timestamp in",
    )

    tag = fields.Char(
        string="Tag",
    )

    payload = fields.Text(
        string="Payload",
    )

    processed = fields.Boolean(
        string="Processed",
    )

    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company)
