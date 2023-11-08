# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, modules
from odoo.exceptions import ValidationError
import requests
import logging
from datetime import datetime
import base64
import uuid

_logger = logging.getLogger(__name__)


class ZcloudDevice(models.Model):
    _name = "z.cloud.device"
    _description = "The device created from Zerynth Cloud"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _rec_name = "device_name"
    _rec_names_search = ['asset_id', 'device_name']
    _order = 'asset_id, id'

    def _default_image(self):
        image_path = modules.get_module_resource(
            'ZcloudApp', 'static/src/img', 'default_device.png')
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
        help="By unchecking the active field, you may hide a DEVICE you will not use.",
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company)

    asset_id = fields.Char(
        string="ID asset",
        tracking=True
    )

    device_name = fields.Char(
        string="Name",
        tracking=True
    )

    device_line_ids = fields.One2many(
        comodel_name="z.cloud.device.line",
        inverse_name="device_id",
        string="Data Processed",
        tracking=True
    )

    # collegamento mrp.workcenter
    workcenter_id = fields.Many2one(
        comodel_name="mrp.workcenter",
        string="Workcenter",
        compute="_compute_workcenter_id",
        store=True,
        tracking=True
    )

    fleet_id = fields.Many2one(
        comodel_name="z.cloud.fleet",
        string="Fleet",
        tracking=True
    )

    workspace_id = fields.Many2one(
        comodel_name="z.cloud.workspace",
        string="Workspace",
        related="fleet_id.workspace_id",
        store=True,
        tracking=True
    )

    action_server_id = fields.Many2one(
        string="Action Server",
        comodel_name="ir.actions.server",
        tracking=True
    )

    @api.depends("workcenter_id.device_id")
    def _compute_workcenter_id(self):
        for record in self:
            record.workcenter_id = self.env["mrp.workcenter"].search(
                [('device_id', '=', record.id)])

    def name_get(self):
        result = []
        for device in self:
            name = ""
            if device.device_name:
                name += device.device_name
            if device.asset_id:
                name = "[%s] " % device.asset_id + name
            result.append((device.id, name))
        return result

    def _parse_raw_data(self):
        """
        Se ci sono righe non processate
        e c'è un'azione allora la lancia (e c'è un workcenter associato)
        ps: l'azione deve avere come modello associato
        z.cloud.device.line perchè la attiviamo su quelle
        """
        for record in self:
            if record.action_server_id and record.workcenter_id:
                lines = record.device_line_ids.filtered(
                    lambda x: not x.processed)
                # ordino le righe per data asc
                lines = lines.sorted(key=lambda x: x.timestamp_device)
                if lines:
                    ctx = {
                        'active_model': 'z.cloud.device.line',
                        'active_ids': lines.ids
                    }
                    record.action_server_id.sudo().with_context(**ctx).run()

    @api.model
    def _cron_parse_raw_data(self):
        """
        Funzione del cron che richiama _parse_raw_data
        """
        devices = self.search([])
        devices._parse_raw_data()

    """
    Questo metodo restituisce un dizionario(forse serve json?) fatto in questo modo:
        - "CHIAVE": ASSET_ID
        - "VALORE": LISTA DI DIZIONARI DI WORKORDER
    ESEMPIO:
        {
            "asset_id_1" : [
                {
                    "id": 3,
                    "name": "asdas",
                    "product_id": {
                        "id": 8,
                        "name": "Desk Combination"
                    },
                    "qty_production": 1.0,
                    "qty_produced": 0.0,
                    "qty_remaning": 1.0,
                    "date_planned_start": false,
                    "duration_expected": 60.0,
                    "date_planned_finished": false,
                    "date_start": false,
                    "date_finished": false,
                    "working_state": "waiting",
                    "workcenter": {
                        "id": 2,
                        "name": "Drill Station 1"
                    }
                },
                {
                    "id": 4,
                    "name": "efwef",
                    "product_id": {
                        "id": 8,
                        "name": "Desk Combination"
                    },
                    "qty_production": 1.0,
                    "qty_produced": 0.0,
                    "qty_remaning": 1.0,
                    "date_planned_start": false,
                    "duration_expected": 0.0,
                    "date_planned_finished": false,
                    "date_start": false,
                    "date_finished": false,
                    "working_state": "waiting",
                    "workcenter": {
                        "id": 2,
                        "name": "Drill Station 1"
                    }
                },
                ecc.. ecc..
            ]
        }
    """

    def get_device_workorders_list(self):
        self.ensure_one()
        device_workorders_dict = {}
        device = self
        # creo un dizionario con chiave asset_id di Zcloud mentre come valore una lista di dizionari di workorder
        if not device.asset_id in device_workorders_dict:
            device_workorders_dict[device.asset_id] = []
        if device.workcenter_id:
            workorder_ids = self.env["mrp.workorder"].sudo().search(
                [("workcenter_id", "=", device.workcenter_id.id)])
            for workorder in workorder_ids:
                workorder_dict = {
                    # id ordine di lavoro
                    "id": workorder.id,
                    # nome ordine di lavoro
                    "name": workorder.name,
                    # prodotto della produzione id e nome
                    "product_id": {
                        "id": workorder.product_id.id,
                        "name":  workorder.product_id.name
                    },
                    # quatità di produzione originale
                    "qty_production": workorder.qty_production,
                    # quantità già prodotta
                    "qty_produced": workorder.qty_produced,
                    # quantità da produrre ancora
                    "qty_remaning": workorder.qty_remaining,
                    # data di inizio programmata
                    "date_planned_start": workorder.date_planned_start,
                    # durata prevista
                    "duration_expected": workorder.duration_expected,
                    # data di fine programmata
                    "date_planned_finished": workorder.date_planned_finished,
                    # data inizio effettiva
                    "date_start": workorder.date_start,
                    # data fine effettiva
                    "date_finished": workorder.date_finished,
                    "working_state": workorder.state,
                    # per debug da togliere
                    "workcenter": {
                        "id": workorder.workcenter_id.id,
                        "name":  workorder.workcenter_id.name
                    },
                }
                device_workorders_dict[device.asset_id].append(
                    workorder_dict)
        return device_workorders_dict

    """
    Funzione che prende i parametri di sistema ZCLOUD_URL e ZCLOUD_API_KEY e restituisce:
        1 error_message = viene valorizzato in caso di errore nel tirare giù i due parametri
        2 ZCLOUD_URL (str)
        3 ZCLOUD_API_KEY (str)
    """
    @api.model
    def _prepare_zcloud_request_parameters(self):
        api_key = self.env['ir.config_parameter'].sudo(
        ).get_param('ZcloudApp.zcloud_api_key')
        if not api_key:
            error_message = _(
                "The API-KEY has not been set in the settings")
            return error_message, False, False
        zcloud_url = self.env['ir.config_parameter'].sudo(
        ).get_param('ZcloudApp.zcloud_url')
        if not zcloud_url:
            error_message = _(
                "The Zcloud url has not been set in the settings")
            return error_message, False, False
        return "", zcloud_url, api_key

    """
    Funzione che crea un ordine e lo avvia su Zcloud
    """

    def create_and_start_order(self, workorder_id=None, part_program_dict={}):
        self.ensure_one()
        _logger.info(_("(DEVICE - CREATE AND START ORDER REQUEST)Executing create_and_start_order on the device name: %s asset_id: %s" % (
            self.device_name, self.asset_id)))
        if isinstance(workorder_id, (str, int)):
            workorder_id = self.env["mrp.workorder"].browse(workorder_id)
        if workorder_id.zcloud_sincronize:
            _logger.error(
                _("(DEVICE - CREATE AND START ORDER REQUEST)ERROR: workorder %s already created on Zcloud" % workorder_id.sequence_name))
            return False
        if not self.workspace_id:
            _logger.error(
                '(DEVICE - CREATE AND START ORDER REQUEST)ERROR: Errore: il device non è collegato ad un workspace')
            self.env['z.cloud.log'].log(
                name="DEVICE - CREATE AND START ORDER REQUEST",
                device_id=self.id,
                response="ERROR: Errore: il device non è collegata ad una workspace(workspace_id=False)",
            )
            return False
        if self.asset_id:
            error_message, zcloud_url, api_key = self._prepare_zcloud_request_parameters()
            if error_message:
                _logger.error(
                    _("(DEVICE - CREATE AND START ORDER REQUEST)ERROR: %s" % error_message))
                self.env['z.cloud.log'].sudo().log(
                    name="DEVICE - CREATE AND START ORDER",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    request="create_and_start_order",
                    response=error_message
                )
                return False
            z_create_and_start_order_url = "%s/workspaces/%s/orders/%s/start?mode=manual" % (
                zcloud_url, self.workspace_id.workspace_id, workorder_id.sequence_name)
            headers = {"X-API-KEY": api_key}
            now_isoformat = datetime.now().replace(microsecond=0).isoformat() + "Z"
            create_start_data = {
                "asset_id": self.asset_id,
                "description": "CREATE AND START: %s" % workorder_id.sequence_name,
                "conf_ts": now_isoformat,
                "start_ts": now_isoformat,
                "provider": self.env['ir.config_parameter'].sudo().get_param('ZcloudApp.zcloud_api_provider') or "odoo",
                "config": {
                    'product': {
                        'id': workorder_id.product_id.id,
                        'name': workorder_id.product_id.name
                    },
                    "quantity": int(workorder_id.qty_production),
                    "workcenter_id": self.workcenter_id.name,
                    "part_program": part_program_dict  # FIX MATTEO: messo qua perchè va dentro config
                },

            }
            try:
                _logger.info(_(
                    '(DEVICE - CREATE AND START ORDER REQUEST) URL: %s DATA: %s' % (z_create_and_start_order_url, create_start_data)))

                response = requests.post(
                    url=z_create_and_start_order_url, headers=headers, json=create_start_data)

                _logger.info(_(
                    '(DEVICE - CREATE AND START ORDER REQUEST) RESPONSE AND RESPONSE CODE %s - %s' % (response, response.status_code)))

                if response.status_code == 200:
                    json_data = response.json()
                    _logger.info(_(
                        "(DEVICE - CREATE AND START ORDER REQUEST) RESPONSE JSON: %s" % json_data))
                    if "error" in json_data and json_data["error"]:
                        _logger.error(
                            "(GET DEVICE JOBS REQUEST)ERROR: 'error' nella response: %s" % json_data["error"])
                        self.env['z.cloud.log'].log(
                            name="DEVICE - CREATE AND START ORDER REQUEST",
                            device_id=self.id,
                            workspace_id=self.workspace_id.id,
                            request=z_create_and_start_order_url,
                            response="ERROR: 'error' nella response: %s" % json_data["error"],
                            status_code=200,
                        )
                        return False
                    self.env['z.cloud.log'].log(
                        name="DEVICE - CREATE AND START ORDER REQUEST: OK",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        request=z_create_and_start_order_url,
                        response="200: DATA: \n%s" % json_data,
                        status_code=200,
                        is_error=False
                    )
                    workorder_id.zcloud_sincronize = True
                    return True
                else:
                    _logger.error(
                        '(CREATE AND START ORDER REQUEST)ERROR: Errore nella richiesta stato: %s, messaggio: %s' % (response.status_code, response.text))
                    self.env['z.cloud.log'].log(
                        name="DEVICE - CREATE AND START ORDER REQUEST",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        response="ERROR: Errore nella richiesta stato: %s, messaggio: %s" % (
                            response.status_code, response.text),
                        request=z_create_and_start_order_url,
                        status_code=response.status_code
                    )
                    return False
            except Exception as error:
                _logger.error(
                    '(DEVICE - CREATE AND START ORDER REQUEST)ERROR EXCEPT: %s' % error)
                self.env['z.cloud.log'].log(
                    name="CREATE AND START ORDER REQUEST",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    response="ERROR EXCEPT: %s" % error,
                    request=z_create_and_start_order_url,
                    status_code=501
                )
                return False
        else:
            _logger.error(
                '(DEVICE - CREATE AND START ORDER REQUEST)ERROR: Errore: il device non ha asset_id')
            self.env['z.cloud.log'].log(
                name="DEVICE - CREATE AND START ORDER REQUEST",
                device_id=self.id,
                workspace_id=self.workspace_id.id,
                response="ERROR: Errore: il device non ha asset_id",
            )
            return False

    """
    Funzione che stoppa un ordine su Zcloud
    """

    def stop_order(self, workorder_id=None):
        self.ensure_one()
        _logger.info(_("(DEVICE - STOP ORDER REQUEST)Executing stop_order on the device name: %s asset_id: %s" % (
            self.device_name, self.asset_id)))
        if isinstance(workorder_id, (str, int)):
            workorder_id = self.env["mrp.workorder"].browse(workorder_id)
        if not workorder_id.zcloud_sincronize:
            _logger.error(
                _("(DEVICE - STOP ORDER REQUEST)ERROR: workorder %s not sincronize on Zcloud" % workorder_id.sequence_name))
            return False
        if workorder_id.zcloud_stop:
            _logger.error(
                _("(DEVICE - STOP ORDER REQUEST)ERROR: workorder %s already stopped on Zcloud" % workorder_id.sequence_name))
            return False
        if not self.workspace_id:
            _logger.error(
                '(DEVICE - STOP ORDER REQUEST)ERROR: Errore: il device non è collegato ad un workspace')
            self.env['z.cloud.log'].log(
                name="DEVICE - STOP ORDER REQUEST",
                device_id=self.id,
                response="ERROR: Errore: il device non è collegata ad una workspace(workspace_id=False)",
            )
            return False
        if self.asset_id:
            error_message, zcloud_url, api_key = self._prepare_zcloud_request_parameters()
            if error_message:
                _logger.error(
                    _("(DEVICE - STOP ORDER REQUEST)ERROR: %s" % error_message))
                self.env['z.cloud.log'].sudo().log(
                    name="DEVICE - STOP ORDER",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    request="stop_order",
                    response=error_message
                )
                return False
            z_stop_order_url = "%s/workspaces/%s/orders/%s/stop?mode=manual" % (
                zcloud_url, self.workspace_id.workspace_id, workorder_id.sequence_name)
            headers = {"X-API-KEY": api_key}
            now_isoformat = datetime.now().replace(microsecond=0).isoformat() + "Z"
            stop_data = {
                "asset_id": self.asset_id,
                "description": "STOP: %s" % workorder_id.sequence_name,
                "end_ts": now_isoformat,
            }
            try:
                _logger.info(_(
                    '(DEVICE - STOP ORDER REQUEST) URL %s' % (z_stop_order_url)))

                response = requests.post(
                    url=z_stop_order_url, headers=headers, json=stop_data)

                _logger.info(_(
                    '(DEVICE - STOP ORDER REQUEST) RESPONSE AND RESPONSE CODE %s - %s' % (response, response.status_code)))

                if response.status_code == 200:
                    json_data = response.json()
                    _logger.info(_(
                        "(DEVICE - STOP ORDER REQUEST) RESPONSE JSON: %s" % json_data))
                    if "error" in json_data and json_data["error"]:
                        _logger.error(
                            "(DEVICE - STOP ORDER REQUEST)ERROR: 'error' nella response: %s" % json_data["error"])
                        self.env['z.cloud.log'].log(
                            name="DEVICE - STOP ORDER REQUEST",
                            device_id=self.id,
                            workspace_id=self.workspace_id.id,
                            request=z_stop_order_url,
                            response="ERROR: 'error' nella response: %s" % json_data["error"],
                            status_code=200,
                        )
                        return False
                    self.env['z.cloud.log'].log(
                        name="DEVICE - STOP ORDER REQUEST: OK",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        request=z_stop_order_url,
                        response="200: DATA: \n%s" % json_data,
                        status_code=200,
                        is_error=False
                    )
                    workorder_id.zcloud_stop = True
                    # self.get_order_data(workorder_id)
                    return True
                else:
                    _logger.error(
                        '(STOP ORDER REQUEST)ERROR: Errore nella richiesta stato: %s' % response.status_code)
                    self.env['z.cloud.log'].log(
                        name="DEVICE - STOP ORDER REQUEST",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        response="ERROR: Errore nella richiesta stato: %s" % response.status_code,
                        request=z_stop_order_url,
                        status_code=response.status_code
                    )
                    return False
            except Exception as error:
                _logger.error(
                    '(DEVICE - STOP ORDER REQUEST)ERROR EXCEPT: %s' % error)
                self.env['z.cloud.log'].log(
                    name="STOP ORDER REQUEST",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    response="ERROR EXCEPT: %s" % error,
                    request=z_stop_order_url,
                    status_code=501
                )
                return False
        else:
            _logger.error(
                '(STOP ORDER REQUEST)ERROR: Errore: il device non ha asset_id')
            self.env['z.cloud.log'].log(
                name="DEVICE - STOP ORDER REQUEST",
                device_id=self.id,
                workspace_id=self.workspace_id.id,
                response="ERROR: Errore: il device non ha asset_id",
            )
            return False

    """
    Funzione che annulla/elimina un ordine su Zcloud
    """

    def delete_order(self, workorder_id=None):
        self.ensure_one()
        _logger.info(_("(DEVICE - DELETE ORDER REQUEST)Executing delete_order on the device name: %s asset_id: %s" % (
            self.device_name, self.asset_id)))
        if isinstance(workorder_id, (str, int)):
            workorder_id = self.env["mrp.workorder"].browse(workorder_id)
        if not workorder_id.zcloud_sincronize:
            _logger.error(
                _("(DEVICE - DELETE ORDER REQUEST)ERROR: workorder %s not sincronize on Zcloud" % workorder_id.sequence_name))
            return False
        if not self.workspace_id:
            _logger.error(
                '(DEVICE - DELETE ORDER REQUEST)ERROR: Errore: il device non è collegato ad un workspace')
            self.env['z.cloud.log'].log(
                name="DEVICE - DELETE ORDER REQUEST",
                device_id=self.id,
                response="ERROR: Errore: il device non è collegata ad una workspace(workspace_id=False)",
            )
            return False
        if self.asset_id:
            error_message, zcloud_url, api_key = self._prepare_zcloud_request_parameters()
            if error_message:
                _logger.error(
                    _("(DEVICE - DELETE ORDER REQUEST)ERROR: %s" % error_message))
                self.env['z.cloud.log'].sudo().log(
                    name="DEVICE - DELETE ORDER",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    request="delete_order",
                    response=error_message
                )
                return False
            z_delete_order_url = "%s/workspaces/%s/orders/%s" % (
                zcloud_url, self.workspace_id.workspace_id, workorder_id.sequence_name)
            headers = {"X-API-KEY": api_key}
            try:
                _logger.info(_(
                    '(DEVICE - DELETE ORDER REQUEST) URL %s' % (z_delete_order_url)))

                response = requests.delete(
                    url=z_delete_order_url, headers=headers)

                _logger.info(_(
                    '(DEVICE - DELETE ORDER REQUEST) RESPONSE AND RESPONSE CODE %s - %s' % (response, response.status_code)))

                if response.status_code == 200:
                    json_data = response.json()
                    _logger.info(_(
                        "(DEVICE - DELETE ORDER REQUEST) RESPONSE JSON: %s" % json_data))
                    if "error" in json_data and json_data["error"]:
                        _logger.error(
                            "(DEVICE - DELETE ORDER REQUEST)ERROR: 'error' nella response: %s" % json_data["error"])
                        self.env['z.cloud.log'].log(
                            name="DEVICE - DELETE ORDER REQUEST",
                            device_id=self.id,
                            workspace_id=self.workspace_id.id,
                            request=z_delete_order_url,
                            response="ERROR: 'error' nella response: %s" % json_data["error"],
                            status_code=200,
                        )
                        return False
                    workorder_id.zcloud_stop = False
                    workorder_id.zcloud_sincronize = False
                    self.env['z.cloud.log'].log(
                        name="DEVICE - DELETE ORDER REQUEST: OK",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        request=z_delete_order_url,
                        response="200: DATA: \n%s" % json_data,
                        status_code=200,
                        is_error=False
                    )
                    return True
                else:
                    _logger.error(
                        '(DELETE ORDER REQUEST)ERROR: Errore nella richiesta stato: %s' % response.status_code)
                    self.env['z.cloud.log'].log(
                        name="DEVICE - DELETE ORDER REQUEST",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        response="ERROR: Errore nella richiesta stato: %s" % response.status_code,
                        request=z_delete_order_url,
                        status_code=response.status_code
                    )
                    return False
            except Exception as error:
                _logger.error(
                    '(DEVICE - DELETE ORDER REQUEST)ERROR EXCEPT: %s' % error)
                self.env['z.cloud.log'].log(
                    name="DELETE ORDER REQUEST",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    response="ERROR EXCEPT: %s" % error,
                    request=z_delete_order_url,
                    status_code=501
                )
                return False
        else:
            _logger.error(
                '(DEVICE - DELETE ORDER REQUEST)ERROR: Errore: il device non ha asset_id')
            self.env['z.cloud.log'].log(
                name="DEVICE - DELETE ORDER REQUEST",
                device_id=self.id,
                workspace_id=self.workspace_id.id,
                response="ERROR: Errore: il device non ha asset_id",
            )
            return False

    def debug_button_get_order_data(self):
        self.ensure_one()
        if self.workcenter_id:
            workorder_ids = self.env["mrp.workorder"].sudo().search(
                [("workcenter_id", "=", self.workcenter_id.id), ("zcloud_stop", "=", True)])
            for workorder in workorder_ids:
                self.get_order_data(workorder)

    """
    Funzione che ottiene i dati di un ordine da Zcloud
    order: [
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
        {
        "start_ts": "{start_ts}",
        "end_ts": "{end_ts}",
        "cons": "{cons}"
        }
    ]
    """

    def get_order_data(self, workorder_id=None):
        self.ensure_one()
        _logger.info(_("(DEVICE - GET ORDER DATA REQUEST)Executing get_order_data on the device name: %s asset_id: %s" % (
            self.device_name, self.asset_id)))
        if isinstance(workorder_id, (str, int)):
            workorder_id = self.env["mrp.workorder"].browse(workorder_id)
        if not workorder_id.zcloud_sincronize or not workorder_id.zcloud_stop:
            _logger.error(
                _("(DEVICE - GET ORDER DATA REQUEST)ERROR: workorder %s not sincronize on Zcloud or not stopped on Zcloud" % workorder_id.sequence_name))
            return False
        if not self.workspace_id:
            _logger.error(
                '(DEVICE - GET ORDER REQUEST)ERROR: Errore: il device non è collegato ad un workspace')
            self.env['z.cloud.log'].log(
                name="DEVICE - GET ORDER REQUEST",
                device_id=self.id,
                response="ERROR: Errore: il device non è collegata ad una workspace(workspace_id=False)",
            )
            return False
        if self.asset_id:
            error_message, zcloud_url, api_key = self._prepare_zcloud_request_parameters()
            if error_message:
                _logger.error(
                    _("(DEVICE - GET ORDER DATA REQUEST)ERROR: %s" % error_message))
                self.env['z.cloud.log'].sudo().log(
                    name="DEVICE - GET ORDER DATA ORDER",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    request="get_order_data",
                    response=error_message
                )
                return False
            z_get_order_data_url = "%s/workspaces/%s/orders/%s/stats" % (
                zcloud_url, self.workspace_id.workspace_id, workorder_id.sequence_name)
            headers = {"X-API-KEY": api_key}
            try:
                _logger.info(_(
                    '(DEVICE - GET ORDER DATA REQUEST) URL %s' % (z_get_order_data_url)))

                response = requests.get(
                    url=z_get_order_data_url, headers=headers)

                _logger.info(_(
                    '(DEVICE - GET ORDER DATA REQUEST) RESPONSE AND RESPONSE CODE %s - %s' % (response, response.status_code)))

                if response.status_code == 200:
                    json_data = response.json()
                    _logger.info(_(
                        "(DEVICE - GET ORDER DATA REQUEST) RESPONSE JSON: %s" % json_data))
                    if "error" in json_data and json_data["error"]:
                        _logger.error(
                            "(DEVICE - GET ORDER DATA REQUEST)ERROR: 'error' nella response: %s" % json_data["error"])
                        self.env['z.cloud.log'].log(
                            name="DEVICE - GET ORDER DATA REQUEST",
                            device_id=self.id,
                            workspace_id=self.workspace_id.id,
                            request=z_get_order_data_url,
                            response="ERROR: 'error' nella response: %s" % json_data["error"],
                            status_code=200,
                        )
                        return False
                    if "order" in json_data and json_data["order"]:
                        workorder_id.zcloud_get_data = True
                        workorder_id.process_zcloud_data_from_list(
                            json_data["order"])
                        self.env['z.cloud.log'].log(
                            name="DEVICE - GET ORDER DATA REQUEST: OK",
                            device_id=self.id,
                            workspace_id=self.workspace_id.id,
                            request=z_get_order_data_url,
                            response="200: DATA: \n%s" % json_data,
                            status_code=200,
                            is_error=False
                        )
                        return True
                    else:
                        _logger.error(
                            "(DEVICE - GET ORDER DATA REQUEST)ERROR: 'order' non è nella response o è vuoto: %s" % json_data["order"])
                        self.env['z.cloud.log'].log(
                            name="DEVICE - GET ORDER DATA REQUEST",
                            device_id=self.id,
                            workspace_id=self.workspace_id.id,
                            request=z_get_order_data_url,
                            response="ERROR: 'order' non è nella response o è vuoto: %s" % json_data[
                                "order"],
                            status_code=200,
                        )
                        return False
                else:
                    _logger.error(
                        '(GET ORDER DATA REQUEST)ERROR: Errore nella richiesta stato: %s' % response.status_code)
                    self.env['z.cloud.log'].log(
                        name="DEVICE - GET ORDER DATA REQUEST",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        response="ERROR: Errore nella richiesta stato: %s" % response.status_code,
                        request=z_get_order_data_url,
                        status_code=response.status_code
                    )
                    return False
            except Exception as error:
                _logger.error(
                    '(DEVICE - GET ORDER DATA REQUEST)ERROR EXCEPT: %s' % error)
                self.env['z.cloud.log'].log(
                    name="GET ORDER DATA REQUEST",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    response="ERROR EXCEPT: %s" % error,
                    request=z_get_order_data_url,
                    status_code=501
                )
                return False
        else:
            _logger.error(
                '(DEVICE - GET ORDER DATA REQUEST)ERROR: Errore: il device non ha asset_id')
            self.env['z.cloud.log'].log(
                name="DEVICE - GET ORDER DATA REQUEST",
                device_id=self.id,
                workspace_id=self.workspace_id.id,
                response="ERROR: Errore: il device non ha asset_id",
            )
            return False

    """
    Funzione che crea il collegamento device - workcenter nella workspace su Zcloud
    """

    def create_connection_asset_workspace(self, workcenter_id=None):
        self.ensure_one()
        _logger.info(_("(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)Executing create_connection_asset_workspace on the device name: %s asset_id: %s" % (
            self.device_name, self.asset_id)))
        if isinstance(workcenter_id, (str, int)):
            workcenter_id = self.env["mrp.workcenter"].browse(workcenter_id)
        if workcenter_id.zcloud_sincronize:
            _logger.error(
                _("(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)ERROR: workcenter %s already sincronize on Zcloud" % workcenter_id))
            return False
        if not self.workspace_id:
            _logger.error(
                '(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)ERROR: Errore: il device non è collegato ad un workspace')
            self.env['z.cloud.log'].log(
                name="DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST",
                device_id=self.id,
                response="ERROR: Errore: il device non è collegata ad una workspace(workspace_id=False)",
            )
            return False
        if self.asset_id:
            error_message, zcloud_url, api_key = self._prepare_zcloud_request_parameters()
            if error_message:
                _logger.error(
                    _("(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)ERROR: %s" % error_message))
                self.env['z.cloud.log'].sudo().log(
                    name="DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    request="create_connection_asset_workspace",
                    response=error_message
                )
                return False
            if not workcenter_id.workcenter_uuid:
                workcenter_id.workcenter_uuid = str(uuid.uuid4())
            z_create_connection_asset_workspace_url = "%s/workspaces/%s/workcenters" % (
                zcloud_url, self.workspace_id.workspace_id)
            headers = {"X-API-KEY": api_key}
            connection_data = {
                "asset_id": self.asset_id,
                "workcenter_id": workcenter_id.workcenter_uuid,
            }
            try:
                _logger.info(_(
                    '(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST) URL %s PARAMS %s' % (z_create_connection_asset_workspace_url, connection_data)))

                response = requests.post(
                    url=z_create_connection_asset_workspace_url, headers=headers, json=connection_data)

                _logger.info(_(
                    '(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST) RESPONSE AND RESPONSE CODE %s - %s' % (response, response.status_code)))

                if response.status_code == 200:
                    json_data = response.json()
                    _logger.info(_(
                        "(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST) RESPONSE JSON: %s" % json_data))
                    if "error" in json_data and json_data["error"]:
                        _logger.error(
                            "(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)ERROR: 'error' nella response: %s" % json_data["error"])
                        self.env['z.cloud.log'].log(
                            name="DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST",
                            device_id=self.id,
                            workspace_id=self.workspace_id.id,
                            request=z_create_connection_asset_workspace_url,
                            response="ERROR: 'error' nella response: %s" % json_data["error"],
                            status_code=200,
                        )
                        return False
                    workcenter_id.zcloud_sincronize = True
                    self.env['z.cloud.log'].log(
                        name="DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST: OK",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        request=z_create_connection_asset_workspace_url,
                        response="200: DATA: \n%s" % json_data,
                        status_code=200,
                        is_error=False,
                        payload=connection_data
                    )
                    return True
                else:
                    _logger.error(
                        '(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)ERROR: Errore nella richiesta stato: %s' % response.status_code)
                    self.env['z.cloud.log'].log(
                        name="DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST",
                        device_id=self.id,
                        workspace_id=self.workspace_id.id,
                        response="ERROR: Errore nella richiesta stato: %s risposta %s" % (
                            response.status_code, response.json()),
                        request=z_create_connection_asset_workspace_url,
                        status_code=response.status_code,
                        payload=connection_data
                    )
                    return False
            except Exception as error:
                _logger.error(
                    '(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)ERROR EXCEPT: %s' % error)
                self.env['z.cloud.log'].log(
                    name="DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST",
                    device_id=self.id,
                    workspace_id=self.workspace_id.id,
                    response="ERROR EXCEPT: %s" % error,
                    request=z_create_connection_asset_workspace_url,
                    status_code=501,
                )
                return False
        else:
            _logger.error(
                '(DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST)ERROR: Errore: il device non ha asset_id')
            self.env['z.cloud.log'].log(
                name="DEVICE - CREATE CONNECTION ASSET WORKSPACE REQUEST",
                device_id=self.id,
                workspace_id=self.workspace_id.id,
                response="ERROR: Errore: il device non ha asset_id",
            )
            return False
