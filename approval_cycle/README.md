# Dynamic Approval System

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

A flexible, rule-based approval workflow system for Odoo that allows administrators to dynamically add approval requirements to any model and method without modifying core code.

## Overview

This module enables Odoo administrators to define approval workflows for any action in the system based on customizable conditions. The system uses Python's introspection capabilities and method patching to intercept method calls, evaluate approval rules, and manage the approval process.

## Features

- **Model Agnostic**: Add approval requirements to any Odoo model
- **Method Selection**: Dynamically discover available methods on models
- **Conditional Rules**: Apply rules based on domain expressions
- **Multi-step Approvals**: Configure sequential approval steps
- **User or Group Approvers**: Assign approvals to specific users or groups
- **Activity Integration**: Automatic activity creation for approvers
- **Chatter Notifications**: Keep users informed of approval status
- **Approval Logs**: Track the complete history of approvals

## Installation

1. Download the module to your Odoo addons directory
2. Install the module through the Odoo Apps menu
3. Configure access rights as needed

## Usage

### Configuring Approval Rules

1. Navigate to **Approvals Configuration > Dynamic Approval Rules**
2. Click "Create" to add a new rule
3. Select the target model and method to intercept
4. Define conditions under which approvals are required using domain expressions
5. Add approval steps with specific users or groups as approvers
6. Set the rule as active

### Approval Process

1. When a user tries to execute a method covered by an approval rule:
   - The system evaluates if the rule applies based on the conditions
   - If approval is needed, the original method execution is intercepted
   - An approval request is created and assigned to the first approver(s)
   
2. Approvers receive notifications and can:
   - Review the request details
   - Approve or reject the request
   - Add rejection reasons when declining

3. After the final approval:
   - The original method is executed automatically
   - The requester receives a notification
   - The approval history is logged

### Managing Approval Requests

Users can view and manage approvals through these menu items:

- **Approvals > To Approve**: Requests waiting for the current user's approval
- **Approvals > My Requests**: Requests created by the current user
- **Approvals > All Requests**: Complete list of all approval requests (admins only)

## Technical Implementation

The module uses several advanced techniques:

- **Method Introspection**: Automatically discovers available methods on models
- **Runtime Method Patching**: Intercepts method calls without modifying core code
- **Python Decorators**: Wraps original methods with approval logic using functools
- **Safe Evaluation**: Uses Odoo's safe_eval for evaluating domain expressions
- **Context Managers**: Uses context flags to avoid infinite recursion when calling original methods

## Compatibility

- Odoo version: 18.0
- Tested on Odoo Community and Enterprise editions

## Support and Development

For questions, issues, or custom development:
- Contact: adham.elsabbagh@gmail.com
- Developer: Adham Elsabbagh <adham.elsabbagh@gmail.com>

---

## License

LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

Copyright 2025 Adham
