# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.resource.models.resource import make_aware
import logging
import json
from dateutil import parser

_logger = logging.getLogger(__name__)


class ZcloudQueue(models.TransientModel):
    _name = "z.cloud.queue"
    _description = "A queue of raw data sent by Zerynth Cloud"
    _transient_max_hours = 2.0
    _order = "create_date desc"

    datas = fields.Text(
        string="Datas"
    )
    processed = fields.Boolean(
        string="Data Processed",
        default=False
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company)

    @api.model
    def _cron_process_zcloudqueue_datas(self):
        cloud_queue_ids = self.search([("processed", "=", False)])
        for cloud_queue in cloud_queue_ids:
            json_data = eval(cloud_queue.datas)
            for result_data in json_data["result"]:
                workspace = self.env["z.cloud.workspace"].search(
                    [("workspace_id", "=", result_data["workspace_id"])])
                if not workspace:
                    workspace = self.env['z.cloud.workspace'].create({
                        'workspace_id': result_data["workspace_id"]
                    })
                fleet = self.env["z.cloud.fleet"].search(
                    [("fleet_id", "=", result_data["fleet_id"])])
                if not fleet:
                    fleet = self.env['z.cloud.fleet'].create({
                        'fleet_id': result_data["fleet_id"]
                    })
                device = self.env["z.cloud.device"].search(
                    ["|", ("device_name", "=", result_data["device_name"]), ("asset_id", "=", result_data["asset_id"])])
                if not device:
                    device = self.env['z.cloud.device'].create({
                        'asset_id': result_data["asset_id"],
                        'device_name': result_data["device_name"]
                    })
                device.fleet_id = fleet.id
                fleet.workspace_id = workspace.id
                # convertiamo le date(creiamo da formato '%Y-%m-%dT%H:%M:%S.%f%z' a '%Y-%m-%d %H:%M:%S')
                # timestamp_device = result_data["timestamp_device"][:10] + " " + result_data["timestamp_device"][11:19]
                # timestamp_in = result_data["timestamp_in"][:10] + " " + result_data["timestamp_in"][11:19]
                timestamp_device = parser.parse(
                    result_data["timestamp_device"]).strftime("%Y-%m-%d %H:%M:%S")
                timestamp_in = parser.parse(
                    result_data["timestamp_in"]).strftime("%Y-%m-%d %H:%M:%S")
                device_line_attrs = {
                    "device_id": device.id,
                    "timestamp_device": timestamp_device,
                    "timestamp_in": timestamp_in,
                    "tag": result_data["tag"],
                    "payload": result_data["payload"],
                }
                self.env["z.cloud.device.line"].create(
                    device_line_attrs)
            cloud_queue.processed = True
