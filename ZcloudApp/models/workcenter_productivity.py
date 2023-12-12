# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpWorkcenterProductivity(models.Model):
    _inherit = "mrp.workcenter.productivity"

    electric_consume = fields.Float(
        string="Electric consume",
        copy=False
    )

    from_zcloud = fields.Boolean(
        string="From Zerynth Platform",
        copy=False
    )
    # pezzi prodotti
    pcs_ok = fields.Float(
        string="Pieces done"
    )
    # pezzi scartati
    pcs_ko = fields.Float(
        string="Pieces discarded"
    )


class MrpWorkcenterProductivityLoss(models.Model):
    _inherit = "mrp.workcenter.productivity.loss"

    is_working = fields.Boolean(
        string="Working",
        copy=False,
        help="Define if is a working phase from Zerynth Platform"
    )
