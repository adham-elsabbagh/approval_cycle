# -*- coding: utf-8 -*-
{
    "name": "Dynamic Approval System",
    "version": "18.0.1.1.0",
    "category": "Extra Tools", 
    "summary": "Generic Dynamic Approval Workflow Engine",
    "description": """
        Allows configuration of dynamic approval workflows for any Odoo model and method.
        - Define rules based on model, method, and conditions.
        - Configure multi-step approvals with specific users or groups.
        - Intercepts method execution until approval is granted.
        - Provides views to manage approval requests.
        - Includes domain builder widget and method suggestion helper.
    """,
    "author": "Centric",
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        # Security first
        "security/security_groups.xml", 
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        # Views
        "views/dynamic_approval_rule_views.xml",
        "views/approval_request_views.xml",
        "views/approval_method_views.xml",
    ],
    "installable": True,
    "application": True, 
    "license": "LGPL-3",
    # "post_init_hook": "_patch_on_load",
}

