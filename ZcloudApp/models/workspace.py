# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, modules
from odoo.exceptions import ValidationError
import requests
import logging
import base64

_logger = logging.getLogger(__name__)


class ZcloudDeviceWorkspace(models.Model):
    _name = "z.cloud.workspace"
    _description = "The workspace of fleets from Zerynth Cloud"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _rec_name = "workspace_id"
    _rec_names_search = ['workspace_id']
    _order = 'workspace_id, id'

    def _default_image(self):
        image_path = modules.get_module_resource(
            'ZcloudApp', 'static/src/img', 'default_workspace.png')
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
        help="By unchecking the active field, you may hide a WORKSPACE you will not use."
    )

    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company)

    workspace_id = fields.Char(
        string="ID workspace",
        tracking=True
    )

    fleet_ids = fields.One2many(
        comodel_name="z.cloud.fleet",
        inverse_name="workspace_id",
        string="Fleets",
        tracking=True
    )

    order_list = fields.Text(
        string="Orders list",
    )

    def name_get(self):
        result = []
        for workspace in self:
            name = ""
            if workspace.workspace_id:
                name += workspace.workspace_id
            result.append((workspace.id, name))
        return result

    def debug_button_get_workspace_order_list(self):
        for record in self:
            record.get_workspace_order_list()

    """
    Funzione che per un workspace ritorna indietro la lista di ordini creati e avviati su Zcloud
    """

    def get_workspace_order_list(self):
        self.ensure_one()
        _logger.info(_("(GET WORKSPACE ORDER LIST REQUEST)Executing get_workspace_order_list on the workspace: %s" % (
            self.workspace_id)))
        if self.workspace_id:
            error_message, zcloud_url, api_key = self.env['z.cloud.device']._prepare_zcloud_request_parameters(
            )
            if error_message:
                _logger.error(
                    _("(GET WORKSPACE ORDER LIST REQUEST)ERROR: %s" % error_message))
                self.env['z.cloud.log'].sudo().log(
                    name="GET WORKSPACE ORDER LIST REQUEST",
                    workspace_id=self.id,
                    request="get_workspace_order_list",
                    response=error_message
                )
                return error_message
            z_get_workspace_order_list_url = "%s/workspaces/%s/orders" % (
                zcloud_url, self.workspace_id)
            headers = {"X-API-KEY": api_key}
            try:
                _logger.info(_(
                    '(GET WORKSPACE ORDER LIST REQUEST) URL %s' % (z_get_workspace_order_list_url)))

                response = requests.get(
                    url=z_get_workspace_order_list_url, headers=headers)

                _logger.info(_(
                    '(GET WORKSPACE ORDER LIST REQUEST) RESPONSE AND RESPONSE CODE %s - %s' % (response, response.status_code)))

                if response.status_code == 200:
                    json_data = response.json()
                    _logger.info(_(
                        "(GET WORKSPACE ORDER LIST REQUEST) RESPONSE JSON: %s" % json_data))
                    self.order_list = json_data
                    if "orders" not in json_data:
                        _logger.error(
                            "(GET WORKSPACE ORDER LIST REQUEST)ERROR: 'orders' non trovato nella response")
                        # errore token non trovato
                        self.env['z.cloud.log'].log(
                            name="GET WORKSPACE ORDER LIST REQUEST",
                            workspace_id=self.id,
                            request=z_get_workspace_order_list_url,
                            response="ERROR: 'orders' non trovato nella response",
                            status_code=200,
                        )
                        return False
                    if "error" in json_data and json_data["error"]:
                        _logger.error(
                            "(GET WORKSPACE ORDER LIST REQUEST)ERROR: 'error' nella response: %s" % json_data["error"])
                        self.env['z.cloud.log'].log(
                            name="GET WORKSPACE ORDER LIST REQUEST",
                            workspace_id=self.id,
                            request=z_get_workspace_order_list_url,
                            response="ERROR: 'error' nella response: %s" % json_data["error"],
                            status_code=200,
                        )
                        return False
                    self.env['z.cloud.log'].log(
                        name="GET WORKSPACE ORDER LIST REQUEST",
                        workspace_id=self.id,
                        request=z_get_workspace_order_list_url,
                        response="200: DATA: \n%s" % json_data,
                        status_code=200,
                        is_error=False
                    )
                    return True
                else:
                    _logger.error(
                        '(GET WORKSPACE ORDER LIST REQUEST)ERROR: Errore nella richiesta stato: %s' % response.status_code)
                    self.env['z.cloud.log'].log(
                        name="GET WORKSPACE ORDER LIST REQUEST",
                        workspace_id=self.id,
                        response="ERROR: Errore nella richiesta stato: %s" % response.status_code,
                        request=z_get_workspace_order_list_url,
                        status_code=response.status_code
                    )
                    return False
            except Exception as error:
                _logger.error(
                    '(GET WORKSPACE ORDER LIST REQUEST)ERROR EXCEPT: %s' % error)
                self.env['z.cloud.log'].log(
                    name="GET WORKSPACE ORDER LIST REQUEST",
                    workspace_id=self.id,
                    response="ERROR EXCEPT: %s" % error,
                    request=z_get_workspace_order_list_url,
                    status_code=501
                )
                return False
        else:
            _logger.error(
                '(GET WORKSPACE ORDER LIST REQUEST)ERROR: Errore: il workspace non ha workspace_id')
            self.env['z.cloud.log'].log(
                name="GET WORKSPACE ORDER LIST REQUEST",
                workspace_id=self.id,
                response="ERROR: Errore: il workspace non ha workspace_id",
            )
            return False
