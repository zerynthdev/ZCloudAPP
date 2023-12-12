# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ZcloudAppSettings(models.TransientModel):
    """
    Estenzione impostazioni di configurazione per impostare le configurazioni di 
    ZcloudApp(connettore con sistemi Zerynth)
    """
    _inherit = 'res.config.settings'
    _description = 'Configuration Settings Extension for Zerynth Platform Connection'

    zcloud_url = fields.Char(
        string="Zerynth Platform Url", config_parameter="ZcloudApp.zcloud_url", default="https://api.zdm.zerynth.com/v3")

    zcloud_api_key = fields.Char(
        string="Zerynth Platform Api Key", config_parameter="ZcloudApp.zcloud_api_key")

    zcloud_api_provider = fields.Char(
        string="Zerynth Platform Api Provider", config_parameter="ZcloudApp.zcloud_api_provider", default="odoo")
