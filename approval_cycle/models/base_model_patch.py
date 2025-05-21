# -*- coding: utf-8 -*-
import logging
import functools
from odoo import api, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.api import Environment

_logger = logging.getLogger(__name__)
_log_prefix = "[DynamicApprovalPatch]"

_original_methods = {}


def _create_dynamic_approval_wrapper(model_name, method_name, original_method):
    """ Creates a wrapper function for a specific method to handle dynamic approvals. """
    _logger.debug(f"{_log_prefix} Creating wrapper for {model_name}.{method_name}")

    @functools.wraps(original_method)
    def wrapper(self, *args, **kwargs):
        _logger.debug(f"{_log_prefix} Wrapper called for {model_name}.{method_name} on records {self.ids}")

        # Check context to bypass approval (used after approval is granted)
        if self.env.context.get('bypass_dynamic_approval'):
            _logger.debug(f"{_log_prefix} Bypassing approval check due to context flag")
            return original_method(self, *args, **kwargs)

        # Use SUPERUSER to check rules and create requests to avoid access right issues
        env_su = self.env(user=SUPERUSER_ID)
        applicable_rules = env_su["dynamic.approval.rule"].search([
            ("model_name", "=", model_name),
            ("method_name", "=", method_name),
            ("active", "=", True)
        ], order="sequence asc")

        if not applicable_rules:
            _logger.debug(f"{_log_prefix} No active rules found, proceeding with original method")
            return original_method(self, *args, **kwargs)

        _logger.info(f"{_log_prefix} Found {len(applicable_rules)} applicable rule(s)")

        # Process records one by one
        records_to_process = self.env[model_name]
        processed_record_ids = set()
        approval_requests_created = []

        for record in self:
            if record.id in processed_record_ids:
                continue

            _logger.debug(f"{_log_prefix} Processing record ID {record.id}")
            record_needs_approval = False
            triggered_rule = None

            # Find first matching rule for this record
            for rule in applicable_rules:
                try:
                    domain = safe_eval(rule.domain or "[]", {"record": record})
                    if record.filtered_domain(domain):
                        _logger.debug(f"{_log_prefix} Rule matched: {rule.name} (ID: {rule.id})")
                        triggered_rule = rule
                        record_needs_approval = True
                        break
                except Exception as e:
                    _logger.error(f"{_log_prefix} Error evaluating domain for rule {rule.id}: {e}")
                    continue

            if not record_needs_approval:
                _logger.debug(f"{_log_prefix} No matching rules, adding to process list")
                processed_record_ids.add(record.id)
                continue

            # Check existing requests
            existing_request = env_su["approval.request"].search([
                ("rule_id", "=", triggered_rule.id),
                ("res_model", "=", model_name),
                ("res_id", "=", record.id)
            ], order="create_date desc", limit=1)

            if existing_request:
                if existing_request.state == "approved":
                    _logger.debug(f"{_log_prefix} Existing approved request found, adding to process list")
                    processed_record_ids.add(record.id)
                    continue
                elif existing_request.state == "pending":
                    _logger.info(f"{_log_prefix} Pending request found: {existing_request.name}")
                    raise UserError(_(
                        "This action requires approval. There's already a pending request:\n"
                        "Request: %s\n"
                        "Status: Waiting for %s"
                    ) % (existing_request.name, existing_request.current_step_id.name))
                elif existing_request.state == "rejected":
                    _logger.info(f"{_log_prefix} Rejected request found: {existing_request.name}")
                    raise UserError(_(
                        "This action was previously rejected.\n"
                        "Request: %s\n"
                        "Reason: %s"
                    ) % (existing_request.name, existing_request.log_ids.filtered(
                        lambda l: l.decision == 'rejected')[:1].reason or "Not specified"))

            # Create new approval request
            first_step = triggered_rule.step_ids.sorted('sequence')[:1]
            if not first_step:
                _logger.error(f"{_log_prefix} No steps configured for rule {triggered_rule.name}")
                raise UserError(_(
                    "Approval rule '%s' is misconfigured (no approval steps). "
                    "Please contact your administrator.") % triggered_rule.name)

            try:
                new_request = env_su['approval.request'].sudo().create({
                    'rule_id': triggered_rule.id,
                    'res_id': record.id,
                    'origin_user_id': self.env.user.id,
                    'current_step_id': first_step.id,
                })
                # Force compute and notifications
                new_request._compute_current_approvers()
                new_request._notify_approvers(first_step)

                approval_requests_created.append(new_request)
                _logger.info(f"""
                {_log_prefix} Created new approval request:
                - Request: {new_request.name} (ID: {new_request.id})
                - Rule: {triggered_rule.name}
                - Record: {model_name}, ID {record.id}
                - Current Step: {first_step.name}
                - Approvers: {new_request.current_approver_ids.mapped('name')}
                """)

            except Exception as e:
                _logger.error(f"{_log_prefix} Failed to create approval request: {e}", exc_info=True)
                raise UserError(_(
                    "Failed to create approval request.\n"
                    "Error details: %s\n\n"
                    "Please contact your administrator.") % str(e))

        if approval_requests_created:
            requests_list = "\n".join([
                f"- {req.name} (Waiting for {req.current_step_id.name})"
                for req in approval_requests_created
            ])
            env_su.cr.commit()  # Force write to database
            raise UserError(_(
                "Action requires approval. The following requests have been created:\n\n"
                "%s\n\n"
                "The approvers have been notified. You'll receive a notification once processed."
            ) % requests_list)

        # Only process records that didn't need approval
        records_to_process = self.filtered(lambda r: r.id in processed_record_ids)
        if records_to_process:
            _logger.debug(f"{_log_prefix} Processing records: {records_to_process.ids}")
            return original_method(records_to_process, *args, **kwargs)

        return None

    return wrapper


def patch_models_for_approval(env):
    """ Patches models based on active dynamic approval rules. """
    _logger.info(f"{_log_prefix} Starting model patching...")
    env_su = env(user=SUPERUSER_ID)

    try:
        rules = env_su["dynamic.approval.rule"].search([("active", "=", True)])
    except Exception as e:
        _logger.error(f"{_log_prefix} Failed to search for rules: {e}")
        return

    patched_methods = set()

    for rule in rules:
        model_name = rule.model_name
        method_name = rule.method_name
        patch_key = (model_name, method_name)

        if not model_name or not method_name:
            continue

        if patch_key in patched_methods:
            continue

        try:
            if model_name not in env:
                _logger.error(f"{_log_prefix} Model not found: {model_name}")
                continue

            ModelClass = env[model_name].__class__
            if not hasattr(ModelClass, method_name):
                _logger.error(f"{_log_prefix} Method not found: {model_name}.{method_name}")
                continue

            original_method = getattr(ModelClass, method_name)

            # Avoid double-patching
            if getattr(original_method, '_is_dynamic_approval_wrapper', False):
                continue

            # Store original method if not already stored
            if patch_key not in _original_methods:
                _original_methods[patch_key] = original_method

            # Create and apply wrapper
            wrapper = _create_dynamic_approval_wrapper(model_name, method_name, original_method)
            wrapper._is_dynamic_approval_wrapper = True
            setattr(ModelClass, method_name, wrapper)
            patched_methods.add(patch_key)

            _logger.info(f"{_log_prefix} Patched {model_name}.{method_name} for rule {rule.name}")

        except Exception as e:
            _logger.error(f"{_log_prefix} Failed to patch {model_name}.{method_name}: {e}")

    _logger.info(f"{_log_prefix} Completed patching. Total methods patched: {len(patched_methods)}")


def _patch_on_load(cr, registry):
    """ Post-init hook to patch models after registry is loaded. """
    env = Environment(cr, SUPERUSER_ID, {})
    _logger.info(f"{_log_prefix} Running post-init hook")
    patch_models_for_approval(env)