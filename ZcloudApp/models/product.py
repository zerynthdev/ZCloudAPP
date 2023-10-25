# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    generic_product = fields.Boolean(
        string='Generic product',
        default=False, # FIX: meglio che il prodotto non sia generico per default
        tracking=True,
        help='This flag is used for the Zcloud Part program. If checked the Part program will be set from the workorder. If not the Part program is taken from the workcenter or the BOM routing'
    )
