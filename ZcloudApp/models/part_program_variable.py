# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, modules
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


""" Classe per configurare le ricette Variabili da inviare alla macchina """


class PartProgramVariable(models.Model):
    _name = "part.program.variable"
    _description = "Class to configure recipes Variables to send to the machine"
    _inherit = ['mail.thread']
    _order = 'sequence,id'

    # archiviato o no
    active = fields.Boolean(
        string="Active",
        default=True,
        help="By unchecking the active field, you may hide a Part Program Variable you will not use.",
        tracking=True
    )

    sequence = fields.Integer(
        string="Sequence",
        copy=False
    )

    name = fields.Text(
        string="Value",
        required=True,
        tracking=True
    )

    workcenter_id = fields.Many2one(
        string="Workcenter",
        comodel_name="mrp.workcenter",
        required=True,
        tracking=True
    )

    def action_open_wizard(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "ZcloudApp.part_program_variable_action_form")
        action['res_id'] = self.id
        return action
