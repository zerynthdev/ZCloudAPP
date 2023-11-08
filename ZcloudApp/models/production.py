# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.tools import float_round


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    workorder_seqcount = fields.Integer(
        string="Workorder sequence count",
        copy=False,
        default=1
    )

    # pezzi prodotti
    pcs_ok = fields.Float(
        string="Pieces done",
        compute="_compute_pcs_ok_pcs_ko_from_last_workorder",
        store=True
    )
    # pezzi scartati
    pcs_ko = fields.Float(
        string="Pieces discarded",
        compute="_compute_pcs_ok_pcs_ko_from_last_workorder",
        store=True
    )
    # vecchio valore dei pezzi scartati
    # (mi serve per creare lo scarto che è la differenza tra nuovo valore e vecchio valore moltiplicato per i componenti)
    old_pcs_ko = fields.Float(
        string="Old Pieces discarded",
        default=0.0
    )

    # compute con la somma dei pezzi prodotti nell'ultimo ordine di lavoro della produzione
    @api.depends('workorder_ids', 'workorder_ids.pcs_ok', 'workorder_ids.pcs_ko')
    def _compute_pcs_ok_pcs_ko_from_last_workorder(self):
        for record in self:
            pcs_ok = 0
            pcs_ko = 0
            if record.workorder_ids:
                # prendo l'ultimo ordine di lavoro
                pcs_ok = sum(record.workorder_ids[len(
                    record.workorder_ids) - 1].mapped('pcs_ok'))
                pcs_ko = sum(record.workorder_ids[len(
                    record.workorder_ids) - 1].mapped('pcs_ko'))
            record.pcs_ok = pcs_ok
            record.pcs_ko = pcs_ko

    # aggiorno la quantità prodotta = pezzi prodotti
    @api.constrains('pcs_ok')
    def _auto_update_qty_producing_from_pcs_ok(self):
        for record in self:
            if record.pcs_ok:
                record.qty_producing = record.pcs_ok

    @api.constrains('qty_producing')
    def _auto_update_component_quantity_done(self):
        for record in self:
            for component in self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                component_done_qty = float_round(
                    record.qty_producing * component.unit_factor, precision_rounding=component.product_uom.rounding)
                component.quantity_done = component_done_qty

    @api.constrains('pcs_ko')
    def _create_scrap_production(self):
        for record in self:
            # calcolo la differenza nuovo valore con vecchio valore
            differenza_scarto = record.pcs_ko - record.old_pcs_ko
            # se è maggiore creo scarto
            if differenza_scarto > 0:
                for component in self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                    component_scrap_qty = float_round(
                        differenza_scarto * component.unit_factor, precision_rounding=component.product_uom.rounding)
                    # controllo che non ci sia già uno scarto per quel prodotto in stato di "Bozza"
                    stock_scrap_id = self.env['stock.scrap'].search([
                        ('production_id', '=', record.id),
                        ('product_id', '=', component.product_id.id),
                        ('company_id', '=', record.company_id.id),
                        ('state', '=', 'draft'),
                    ])
                    if stock_scrap_id:
                        stock_scrap_id.scrap_qty += component_scrap_qty
                    else:
                        stock_scrap_id = self.env['stock.scrap'].create({
                            'production_id': record.id,
                            'product_id': component.product_id.id,
                            'company_id': record.company_id.id,
                            'scrap_qty': component_scrap_qty
                        })
                    # TODO: in futuro magari ci sarà l'autovalidazione dello scarto(nel caso scommentare codice sotto)
                    # stock_scrap_id.action_validate()
            # aggiorno il vecchio valore
            record.old_pcs_ko = record.pcs_ko
