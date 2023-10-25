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
            # se è un dict allora mi sta inviando i dati grezzi
            if isinstance(json_data, dict):
                if "result" in json_data["result"]:
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
            # adesso manda una lista con i dati puliti
            if isinstance(json_data, list):
                for result_data in json_data:
                    # AGGIUNTA DELLA CREAZIONE DEI FLEET E DEI WORKSPACE
                    workspace = False
                    fleet = False
                    if "workspace_id" in result_data and result_data["workspace_id"]:
                        workspace = self.env["z.cloud.workspace"].search(
                            [("workspace_id", "=", result_data["workspace_id"])])
                        if not workspace:
                            workspace = self.env['z.cloud.workspace'].create({
                                'workspace_id': result_data["workspace_id"]
                            })
                    if "fleet_id" in result_data and result_data["fleet_id"]:
                        fleet = self.env["z.cloud.fleet"].search(
                            [("fleet_id", "=", result_data["fleet_id"])])
                        if not fleet:
                            fleet = self.env['z.cloud.fleet'].create({
                                'fleet_id': result_data["fleet_id"]
                            })
                    if "asset_id" in result_data and "device_id" in result_data:
                        device = self.env["z.cloud.device"].search(
                            ["|", ("device_name", "=", result_data["device_id"]), ("asset_id", "=", result_data["asset_id"])])
                        if not device:
                            device = self.env['z.cloud.device'].create({
                                'asset_id': result_data["asset_id"],
                                'device_name': result_data["device_id"]
                            })
                        # assegno fleet e workspace
                        if fleet and workspace:
                            device.fleet_id = fleet.id
                            fleet.workspace_id = workspace.id
                        # convertiamo le date(creiamo da formato '%Y-%m-%dT%H:%M:%S.%f%z' a '%Y-%m-%d %H:%M:%S')
                        start = parser.parse(
                            result_data["start"]).strftime("%Y-%m-%d %H:%M:%S")
                        end = parser.parse(
                            result_data["end"]).strftime("%Y-%m-%d %H:%M:%S")
                        device_line_attrs = {
                            "device_id": device.id,
                            "timestamp_device": start,
                            "timestamp_in": end,
                            "payload": result_data,
                        }
                        self.env["z.cloud.device.line"].create(
                            device_line_attrs)
                        # se è presente 'order_id' lo cerco in odoo, se lo trovo allora
                        # faccio l'aggiornamento dei dati del workorder con quelli ricevuti da Zcloud
                        if result_data["order_id"]:
                            workorder_id = self.env['mrp.workorder'].search(
                                [('sequence_name', '=', result_data["order_id"])])
                            # se trovo l'ordine in odoo allora aggiorno i dati
                            if workorder_id:
                                workorder_id.process_zcloud_data_from_list(
                                    [result_data])
                            # se non trovo l'ordine in odoo allora creo la riga nella tabella z.cloud.data
                            else:
                                z_cloud_data_attr = {
                                    "device_id": device.id,
                                    "date_start": start,
                                    "date_end": end,
                                    "status": result_data['status'],
                                    "electric_consume": result_data['cons'],
                                    "zcloud_json_data": result_data,
                                    "workorder_not_found": result_data['order_id'],
                                    "is_working": bool(result_data['status_code']),
                                }
                                if "pcs_ok" in result_data:
                                    try:
                                        pcs_ok = float(result_data["pcs_ok"])
                                    except:
                                        pcs_ok = 0
                                    z_cloud_data_attr["pcs_ok"] = pcs_ok
                                if "pcs_ko" in result_data:
                                    try:
                                        pcs_ko = float(result_data["pcs_ko"])
                                    except:
                                        pcs_ko = 0
                                    z_cloud_data_attr["pcs_ko"] = pcs_ko
                                self.env["z.cloud.data"].create(
                                    z_cloud_data_attr)
                        # se non è presente 'order_id' creo una riga nella tabella z.cloud.data che
                        # permette ad un utente di associare i dati orfani ad un ordine di lavoro di Odoo
                        else:
                            z_cloud_data_attr = {
                                "device_id": device.id,
                                "date_start": start,
                                "date_end": end,
                                "status": result_data['status'],
                                "electric_consume": result_data['cons'],
                                "zcloud_json_data": result_data,
                                "is_working": bool(result_data['status_code']),
                            }
                            if "pcs_ok" in result_data:
                                try:
                                    pcs_ok = float(result_data["pcs_ok"])
                                except:
                                    pcs_ok = 0
                                z_cloud_data_attr["pcs_ok"] = pcs_ok
                            if "pcs_ko" in result_data:
                                try:
                                    pcs_ko = float(result_data["pcs_ko"])
                                except:
                                    pcs_ko = 0
                                z_cloud_data_attr["pcs_ko"] = pcs_ko
                            self.env["z.cloud.data"].create(
                                z_cloud_data_attr)
            cloud_queue.processed = True
