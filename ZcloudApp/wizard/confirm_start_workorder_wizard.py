# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class ConfirmStartWorkorderWizard(models.TransientModel):
    _name = "confirm.start.workorder.wizard"
    _description = "wizard to confirm the start of a new workorder. Only dipslay if Zcloud configuration of workcenter are active"

    workorder_id = fields.Many2one(
        string="Workorder",
        comodel_name="mrp.workorder"
    )

    workorder_ids = fields.Many2many(
        string="Workorders",
        comodel_name="mrp.workorder"
    )

    # creo un html per il wizard per mostrare il messaggio in html
    wizard_text_html = fields.Text(
        string="Wizad text html",
    )

    def confirm_start(self):
        if self.workorder_id:
            self.workorder_id.with_context(
                wizard_start_confirm=True).button_start()
            return True
        else:
            raise UserError(
                _("There isn't a workorder related to this wizard. Close the wizard and try again"))

    def continue_without_stop(self):
        if self.workorder_id:
            self.workorder_id.with_context(
                wizard_continue_without_stop=True).button_start()
            return True
        else:
            raise UserError(
                _("There isn't a workorder related to this wizard. Close the wizard and try again"))
