# -*- coding: utf-8 -*-
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ZCloudLog(models.Model):
    _name = "z.cloud.log"
    _description = "Log of the request to Zerynth Platform"

    datelog = fields.Datetime(string="Date")
    device_id = fields.Many2one(
        string="Device",
        comodel_name="z.cloud.device",
    )
    workspace_id = fields.Many2one(
        string="Workspace",
        comodel_name="z.cloud.workspace",
    )
    response = fields.Text(string="Response")
    request = fields.Text(string="Request")
    payload = fields.Text(string="Payload")
    status_code = fields.Text(string="Status code")
    name = fields.Char(string="Call request")
    is_error = fields.Boolean(string="Is error", default=True)

    @api.model
    def log(self, name=False, device_id=False, workspace_id=False, is_error=True, response=False, payload=False, status_code=False, request=False):
        attrs = {
            'datelog': datetime.datetime.now(),
            'device_id': device_id,
            'workspace_id': workspace_id,
            'response': response,
            'payload': payload,
            'request': request,
            'name': name,
            'is_error': is_error
        }
        self.sudo().create(attrs)
