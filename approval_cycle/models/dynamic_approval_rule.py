# -*- coding: utf-8 -*-
import inspect
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class DynamicApprovalRule(models.Model):
    """ Defines the rules for triggering dynamic approvals. """
    _name = "dynamic.approval.rule"
    _description = "Dynamic Approval Rule"
    _order = "sequence, name"

    name = fields.Char(string="Rule Name", required=True, help="A descriptive name for the approval rule.")
    sequence = fields.Integer(string="Sequence", default=10, help="Determines the order of evaluation if multiple rules could apply.")
    model_id = fields.Many2one(
        "ir.model", 
        string="Model", 
        required=True, 
        ondelete="cascade",
        help="Select the Odoo model this rule applies to (e.g., Sale Order, Invoice)."
    )
    model_name = fields.Char(related="model_id.model", string="Model Name", store=True, readonly=True)
    method_name = fields.Char(
        string="Method Name", 
        required=True, 
        help="Specify the technical name of the Python method on the model that triggers this approval (e.g., action_confirm, action_post). Ensure it's a public method."
    )
    domain = fields.Char(
        string="Apply On", 
        default="[]", 
        required=True,
        help="Conditions under which this rule applies. Use Odoo domain syntax (e.g., [('amount_total', '>', 1000)])."
    )
    step_ids = fields.One2many(
        "dynamic.approval.rule.step", 
        "rule_id", 
        string="Approval Steps",
        copy=True,
        help="Define the sequence of approval steps required."
    )
    active = fields.Boolean(string="Active", default=True, help="Uncheck to disable this rule without deleting it.")
    method_selection_id = fields.Many2one(
        'studio.approval.method',
        string="Available Method",
        domain="[('model_id', '=', model_id)]"
    )

    @api.onchange('method_selection_id')
    def _onchange_method_selection_id(self):
        if self.method_selection_id:
            self.method_name = self.method_selection_id.name

    # --- Introspection Methods --- #

    @api.onchange("model_id")
    def _onchange_model_id(self):
        if self.model_id:
            self._populate_available_methods(self.model_id)

    def _populate_available_methods(self, model):
        methods = self._get_methods_for_model(model.model)
        existing = self.env["studio.approval.method"].search(
            [("model_id", "=", model.id)]
        )
        existing_names = {rec.name for rec in existing}
        new_names = {name for name, _ in methods}

        if existing_names != new_names:
            existing.unlink()
            for name, label in methods:
                self.env["studio.approval.method"].create(
                    {
                        "name": name,
                        "label": label,
                        "model_id": model.id,
                    }
                )

    def _get_methods_for_model(self, model_name):
        method_list = []
        try:
            model_cls = self.env[model_name].__class__
            for name, _func in inspect.getmembers(model_cls, inspect.isfunction):
                if not name.startswith("_") and name not in [
                    "create",
                    "write",
                    "unlink",
                    "read",
                    "search",
                    "browse",
                ]:
                    label = name.replace("action_", "").replace("_", " ").capitalize()
                    method_list.append((name, label))
        except Exception as e:
            _logger.error(f"Error introspecting methods for model {model_name}: {e}")
        return method_list

class DynamicApprovalRuleStep(models.Model):
    """ Defines a single step in a dynamic approval rule sequence. """
    _name = "dynamic.approval.rule.step"
    _description = "Dynamic Approval Rule Step"
    _order = "sequence, id"

    rule_id = fields.Many2one("dynamic.approval.rule", string="Rule", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Step Sequence", default=10, required=True, help="Order of this step in the approval process.")
    name = fields.Char(string="Step Name", compute="_compute_name", store=True, help="Computed name for the step.")
    approver_type = fields.Selection(
        [("user", "Specific User"), ("group", "User Group")], 
        string="Approver Type", 
        default="user", 
        required=True,
        help="Specify whether approval is required from a specific user or any member of a group."
    )
    user_id = fields.Many2one(
        "res.users", 
        string="Approving User", 
        domain=[("share", "=", False)], # Exclude portal/internal share users
        help="Select the specific user required to approve this step."
    )
    group_id = fields.Many2one(
        "res.groups", 
        string="Approving Group", 
        help="Select the user group whose members can approve this step."
    )

    _sql_constraints = [
        ("approver_required", 
         "CHECK((approver_type = \'user\' AND user_id IS NOT NULL) OR (approver_type = \'group\' AND group_id IS NOT NULL))",
         "An approving user or group must be specified for each step.")
    ]

    @api.depends("approver_type", "user_id", "group_id", "sequence")
    def _compute_name(self):
        for step in self:
            name = f"Step {step.sequence}"
            if step.approver_type == "user" and step.user_id:
                name += f": {step.user_id.name}"
            elif step.approver_type == "group" and step.group_id:
                name += f": {step.group_id.name}"
            step.name = name

