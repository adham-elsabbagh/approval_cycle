from odoo import models, api
from . import base_model_patch


class DynamicApprovalPatchHandler(models.Model):
    _name = 'dynamic.approval.patch.handler'
    _description = 'Handles dynamic approval method patching'

    @api.model
    def _register_hook(self):
        super()._register_hook()
        base_model_patch.patch_models_for_approval(self.env)