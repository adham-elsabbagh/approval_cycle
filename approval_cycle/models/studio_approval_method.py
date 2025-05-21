# Copyright 2025 Centric
# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl-3.0).
# @author Adham Mohamed <adham.mohamed@centric.eu>

from odoo import fields, models, api


class StudioApprovalMethod(models.Model):
    _name = 'studio.approval.method'
    _description = 'Available Method for Approval'
    _rec_name = 'label'

    name = fields.Char(required=True)
    label = fields.Char(required=True)
    model_id = fields.Many2one('ir.model', string='Model', ondelete='cascade', required=True)
