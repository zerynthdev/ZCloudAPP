# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    # booleano per identificare gli allegati del part program
    is_part_program = fields.Boolean(
        string="Part program",
    )
