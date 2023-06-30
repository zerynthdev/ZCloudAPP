# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, modules
from odoo.exceptions import ValidationError
import base64


class ZcloudDeviceFleet(models.Model):
    _name = "z.cloud.fleet"
    _description = "The fleet of devices from Zerynth Cloud"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _rec_name = "fleet_id"
    _rec_names_search = ['fleet_id']
    _order = 'fleet_id, id'

    def _default_image(self):
        image_path = modules.get_module_resource(
            'ZcloudApp', 'static/src/img', 'default_fleet.png')
        return base64.b64encode(open(image_path, 'rb').read())

    image_1920 = fields.Image(
        string="Image",
        max_width=1920,
        max_height=1920,
        default=_default_image
    )

    # archiviato o no
    active = fields.Boolean(
        string="Active",
        default=True,
        help="By unchecking the active field, you may hide a FLEET you will not use."
    )

    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company)

    fleet_id = fields.Char(
        string="ID fleet",
        tracking=True
    )

    device_ids = fields.One2many(
        comodel_name="z.cloud.device",
        inverse_name="fleet_id",
        string="Devices",
        tracking=True
    )

    workspace_id = fields.Many2one(
        comodel_name="z.cloud.workspace",
        string="Workspace",
        tracking=True
    )

    def name_get(self):
        result = []
        for fleet in self:
            name = ""
            if fleet.fleet_id:
                name += fleet.fleet_id
            if fleet.workspace_id:
                name = "[%s] " % fleet.workspace_id.workspace_id + name
            result.append((fleet.id, name))
        return result
