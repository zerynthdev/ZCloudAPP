# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ZcloudAppSettings(models.TransientModel):
    """
    Estenzione impostazioni di configurazione per impostare le configurazioni di 
    ZcloudApp(connettore con sistemi Zerynth)
    """
    _inherit = 'res.config.settings'
    _description = 'Estenzione impostazioni di configurazione per ZcloudApp connessione Zerynth'

    zcloud_url = fields.Char(
        string="Zcloud Url", config_parameter="ZcloudApp.zcloud_url")

    zcloud_api_key = fields.Char(
        string="Zcloud Api Key", config_parameter="ZcloudApp.zcloud_api_key")

    zcloud_api_provider = fields.Char(
        string="Zcloud Api Provider", config_parameter="ZcloudApp.zcloud_api_provider", default="odoo")
