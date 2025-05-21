# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ApprovalRequest(models.Model):
    """ Represents a specific instance of an approval process triggered by a rule. """
    _name = "approval.request"
    _description = "Approval Request"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Request Name", compute="_compute_name", store=True)
    rule_id = fields.Many2one(
        "dynamic.approval.rule", 
        string="Triggering Rule", 
        required=True, 
        ondelete="restrict",
    )
    res_model_id = fields.Many2one(
        "ir.model", 
        string="Resource Model", 
        related="rule_id.model_id", 
        store=True, 
        readonly=True
    )
    res_model = fields.Char(string="Resource Model Name", related="res_model_id.model", store=True, readonly=True)
    res_id = fields.Integer(string="Resource ID", required=True, readonly=True, index=True)
    resource_ref = fields.Reference(
        string="Document", 
        selection="_selection_target_model", 
        compute="_compute_resource_ref", 
        readonly=True
    )
    origin_user_id = fields.Many2one(
        "res.users", 
        string="Requested By", 
        default=lambda self: self.env.user,
        readonly=True
    )
    request_date = fields.Datetime(string="Requested On", default=fields.Datetime.now, readonly=True)
    
    state = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancel", "Cancelled"),
    ], string="Status", default="pending", tracking=True, required=True, copy=False)

    current_step_id = fields.Many2one(
        "dynamic.approval.rule.step", 
        string="Current Step", 
        readonly=True, 
        copy=False,
        help="The current step waiting for approval."
    )
    current_approver_ids = fields.Many2many(
        "res.users",
        store=True,
        string="Current Approvers", 
        compute="_compute_current_approvers",
        help="Users who can currently approve this request."
    )
    can_user_approve = fields.Boolean(string="Can Current User Approve?", compute="_compute_can_user_approve")

    log_ids = fields.One2many("approval.request.log", "request_id", string="Approval Log", readonly=True)

    @api.depends("rule_id.name", "res_model", "res_id")
    def _compute_name(self):
        for req in self:
            name = req.rule_id.name or "Approval Request"
            if req.res_model and req.res_id:
                try:
                    record_name = self.env[req.res_model].browse(req.res_id).display_name
                    name = f"{name} for {record_name or f'{req.res_model}/{req.res_id}'}"
                except Exception:
                    name = f"{name} for {req.res_model}/{req.res_id}"
            req.name = name

    @api.model
    def _selection_target_model(self):
        return [(model.model, model.name) for model in self.env["ir.model"].sudo().search([])]

    @api.depends("res_model", "res_id")
    def _compute_resource_ref(self):
        for req in self:
            if req.res_model and req.res_id:
                req.resource_ref = f"{req.res_model},{req.res_id}"
            else:
                req.resource_ref = False

    @api.depends("current_step_id", "current_step_id.approver_type", "current_step_id.user_id", "current_step_id.group_id", "current_step_id.group_id.users")
    def _compute_current_approvers(self):
        for req in self:
            if req.state == "pending" and req.current_step_id:
                if req.current_step_id.approver_type == "user":
                    req.current_approver_ids = req.current_step_id.user_id
                elif req.current_step_id.approver_type == "group":
                    req.current_approver_ids = req.current_step_id.group_id.users
                else:
                    req.current_approver_ids = False
            else:
                req.current_approver_ids = False
                
    @api.depends("current_approver_ids")
    def _compute_can_user_approve(self):
        for req in self:
            req.can_user_approve = self.env.user in req.current_approver_ids

    # --- Action Methods --- #

    def action_approve(self):
        self.ensure_one()
        if not self.can_user_approve:
            raise UserError(_("You are not authorized to approve this request at the current step."))
        if self.state != "pending":
            raise UserError(_("This request is not in a pending state."))

        self._create_log_entry("approved")
        next_step = self._find_next_step()

        if next_step:
            self.write({"current_step_id": next_step.id})
            self._notify_approvers(next_step)
        else:
            self.write({"state": "approved", "current_step_id": False})
            self._trigger_original_method() # The core logic!
            self._notify_requester("approved")
            self._clear_activities()

    def action_reject(self):
        self.ensure_one()
        if not self.can_user_approve:
            raise UserError(_("You are not authorized to reject this request at the current step."))
        if self.state != "pending":
            raise UserError(_("This request is not in a pending state."))
        
        # TODO: Add a wizard to ask for rejection reason?
        rejection_reason = "Rejected by user."
        self._create_log_entry("rejected", reason=rejection_reason)
        self.write({"state": "rejected", "current_step_id": False})
        self._notify_requester("rejected", reason=rejection_reason)
        self._clear_activities()


    def _create_log_entry(self, decision, reason=None):
        self.ensure_one()
        self.env["approval.request.log"].sudo().create({
            "request_id": self.id,
            "step_id": self.current_step_id.id,
            "decision": decision,
            "decision_date": fields.Datetime.now(),
            "user_id": self.env.user.id,
            "reason": reason,
        })

    def _find_next_step(self):
        self.ensure_one()
        current_sequence = self.current_step_id.sequence
        next_step = self.env["dynamic.approval.rule.step"].search([
            ("rule_id", "=", self.rule_id.id),
            ("sequence", ">", current_sequence)
        ], order="sequence asc", limit=1)
        return next_step

    def _trigger_original_method(self):
        """ This is where the magic happens after approval. Needs careful implementation. """
        self.ensure_one()
        _logger.info(f"Approval granted for {self.res_model} {self.res_id}, method {self.rule_id.method_name}. Triggering original method.")
        record = self.env[self.res_model].browse(self.res_id)
        # How to call the original method safely?
        # This requires the patching mechanism to store the original method
        # and provide a way to call it, bypassing the wrapper for this specific record.
        # Placeholder for now.
        try:
            # We need access to the original arguments (*args, **kwargs) if any were passed.
            # This is a major challenge - how to store/retrieve them?
            # Maybe the wrapper needs to store them on the request?
            
            # Simplistic approach for methods without args for now:
            # getattr(record, self.rule_id.method_name)()
            
            # A more robust approach might involve a flag or context:
            record.with_context(bypass_dynamic_approval=self.rule_id.id).mapped(self.rule_id.method_name)
            
            # Post a success message?
            record.message_post(body=_(f"Action '{self.rule_id.method_name}' executed after approval."))

        except Exception as e:
            _logger.error(f"Error triggering original method {self.rule_id.method_name} for {self.res_model} {self.res_id}: {e}")
            # Maybe notify the user?
            self.message_post(
                body=_("⚠️ Failed to execute action '%s' after approval. Error: %s" % (self.rule_id.method_name, e))
            )

    def _notify_approvers(self, step_to_notify):
        self.ensure_one()
        approvers = self.env["res.users"]
        if step_to_notify.approver_type == "user":
            approvers = step_to_notify.user_id
        elif step_to_notify.approver_type == "group":
            approvers = step_to_notify.group_id.users
        
        if approvers:
            record_ref = self.resource_ref
            for approver in approvers:
                self.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=approver.id,
                    note=_("Please approve %s for %s.") % (record_ref.display_name if record_ref else f"{self.res_model}/{self.res_id}", step_to_notify.name),
                    summary=_("Approval Required"),
                )
            # TODO: Add email notifications?

    def _notify_requester(self, status, reason=None):
        self.ensure_one()
        record_ref = self.resource_ref
        doc_name = record_ref.display_name if record_ref else f"{self.res_model}/{self.res_id}"

        if status == "approved":
            message = _("Your request to approve %s has been fully approved.") % doc_name
        elif status == "rejected":
            message = _("Your request to approve %s has been rejected.") % doc_name
            if reason:
                message += _(" Reason: %s") % reason
        else:
            message = _("Your request for %s has been updated.") % doc_name

        # Notify via internal message
        self.env['mail.message'].sudo().create({
            'author_id': self.env.user.partner_id.id,
            'model': 'res.users',
            'res_id': self.origin_user_id.id,
            'message_type': 'notification',
            'subtype_id': self.env.ref('mail.mt_note').id,
            'body': message,
        })

        self.message_post(body=message)

    def _clear_activities(self):
        self.activity_unlink(["mail.mail_activity_data_todo"]) # Clear approval activities


class ApprovalRequestLog(models.Model):
    """ Logs the history of decisions for an approval request. """
    _name = "approval.request.log"
    _description = "Approval Request Log"
    _order = "decision_date desc"

    request_id = fields.Many2one("approval.request", string="Request", required=True, ondelete="cascade")
    step_id = fields.Many2one("dynamic.approval.rule.step", string="Step", readonly=True)
    decision = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], string="Decision", required=True, readonly=True)
    decision_date = fields.Datetime(string="Decision Date", required=True, readonly=True)
    user_id = fields.Many2one("res.users", string="Decided By", readonly=True)
    reason = fields.Text(string="Reason", readonly=True)

