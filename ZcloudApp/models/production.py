# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    workorder_seqcount = fields.Integer(
        string="Workorder sequence count",
        copy=False,
        default=1
    )
