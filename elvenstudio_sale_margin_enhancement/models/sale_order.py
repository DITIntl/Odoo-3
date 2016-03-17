# -*- coding: utf-8 -*-

import logging

from openerp import api, fields, models
import openerp.addons.decimal_precision as dp

_log = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Rewrite margin field for odoo 8 compatibility
    margin = fields.Float(compute='_product_margin', digits=dp.get_precision('Product Price'), store=True)

    @api.multi
    @api.onchange('product_id', 'product_uom_qty', 'order_id.pricelist_id')
    def product_id_change_margin(self):
        for line in self:
            if line.order_id.pricelist_id:
                pricelist = line.order_id.pricelist_id
                frm_cur = self.env.user.company_id.currency_id
                to_cur = pricelist.currency_id

                purchase_price = pricelist.with_context(product_id=line.product_id.id).product_cost or line.product_id.standard_price

                if line.product_uom != line.product_id.uom_id:
                    purchase_price = self.env['product.uom']._compute_price(
                        line.product_id.uom_id.id,
                        purchase_price,
                        to_uom_id=line.product_uom.id
                    )

                ctx = self.env.context.copy()
                ctx['date'] = line.order_id.date_order
                price = frm_cur.with_context(ctx).compute(purchase_price, to_cur, round=False)
                line.purchase_price = price

    @api.multi
    @api.depends('product_id', 'purchase_price', 'product_uom_qty', 'price_unit')
    def _product_margin(self):
        for line in self:
            currency = line.order_id.pricelist_id.currency_id
            line.margin = currency.round(
                line.price_subtotal - ((line.purchase_price or line.product_id.standard_price) * line.product_uom_qty)
            )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Rewrite margin field for odoo 8 compatibility
    margin = fields.Float(
        compute='_product_margin',
        currency_field='currency_id',
        digits=dp.get_precision('Product Price'),
        store=True,
        help="It gives profitability by calculating the difference between the Unit Price and the cost."
    )

    @api.multi
    @api.depends('order_line.margin')
    def _product_margin(self):
        for order in self:
            order.margin = sum(order.order_line.filtered(lambda r: r.state != 'cancel').mapped('margin'))

    @api.multi
    def recompute_order_margin(self):
        for order in self:
            order.order_line.product_id_change_margin()
            order.order_line._product_margin()

        self._product_margin()