# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpRoutingWorkcenter(models.Model):
    _name = "mrp.routing.workcenter"
    _inherit = ['mrp.routing.workcenter', 'mail.thread']

    # part program
    part_program_type = fields.Selection(
        string="Part program",
        related="workcenter_id.part_program_type",
        store=True,
        tracking=True
    )
    part_program_file = fields.Binary(
        string="File",
        tracking=True
    )
    part_program_file_name = fields.Char(
        string="File name",
        tracking=True
    )

    # creo un allegato
    @api.constrains('part_program_file', 'part_program_file_name')
    def add_attachment_to_routing_workcenter(self):
        for record in self:
            if record.part_program_file:
                # TODO: chiedere a Matteo
                # elimino i vecchi file part program collegati a questo record(per non sovraccaricare)
                old_part_program_files = self.env['ir.attachment'].sudo().search(
                    [('res_model', '=', 'mrp.routing.workcenter'), ('is_part_program', '=', True), ('res_id', '=', record.id)])
                old_part_program_files.unlink()
                attachment_attr = {
                    'name': record.part_program_file_name,
                    'type': 'binary',
                    'res_model': 'mrp.routing.workcenter',
                    'res_id': record.id,
                    'datas': record.part_program_file,
                    'is_part_program': True
                }
                self.env['ir.attachment'].sudo().create(attachment_attr)

    part_program_url = fields.Char(
        string="Url",
        tracking=True
    )
    part_program_path = fields.Char(
        string="Path",
        tracking=True
    )
    part_program_variable = fields.Many2one(
        string="Variable",
        comodel_name="part.program.variable",
        domain="[('workcenter_id', '=', workcenter_id)]",
        copy=False
    )
    part_program_json = fields.Text(
        string="Json",
        tracking=True
    )

    """
    FUNZIONE CHE RITORNA UN DIZIONARIO PER IL PART PROGRAM COSÌ:
        -  CHIAVE: part_program_type VALORE: part_program_type ('file', 'path', 'variable', 'json')
        -  CHIAVE: part_program_data VALORE: part_program_(campo corrispondente al type)
    """

    def create_part_program_dict_from_routing(self):
        self.ensure_one()
        part_program_dict = {}
        if self.part_program_type == 'file':
            if self.part_program_file:
                # ricerco l'allegato
                attachment = self.env['ir.attachment'].sudo().search(
                    [('res_id', '=', self.id), ('res_model', '=', 'mrp.routing.workcenter'), ('name', '=', self.part_program_file_name)], limit=1)
                if attachment:
                    attachment.generate_access_token()
                    odoo_url = self.env['ir.config_parameter'].sudo(
                    ).get_param('web.base.url')
                    attachment_url = odoo_url + \
                        '/web/content?id={}&access_token={}'.format(
                            attachment.id, attachment.access_token)
                    part_program_dict['part_program_type'] = self.part_program_type
                    part_program_dict['part_program_data'] = attachment_url
            if self.part_program_url:
                part_program_dict['part_program_type'] = self.part_program_type
                part_program_dict['part_program_data'] = self.part_program_url
        if self.part_program_type == 'path':
            if self.part_program_path:
                part_program_dict['part_program_type'] = self.part_program_type
                part_program_dict['part_program_data'] = self.part_program_path
        if self.part_program_type == 'variable':
            if self.part_program_variable:
                part_program_dict['part_program_type'] = self.part_program_type
                part_program_dict['part_program_data'] = self.part_program_variable.name
        if self.part_program_type == 'json':
            if self.part_program_json:
                part_program_dict['part_program_type'] = self.part_program_type
                try:
                    json_data = eval(self.part_program_json)
                except Exception as error:
                    raise UserError(
                        _("There was an error reading the Json, please check the json in the BOM.\nError: %s" % error))
                part_program_dict['part_program_data'] = json_data
        return part_program_dict
