# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ShiftAssignmentWizard(models.TransientModel):
    _name = 'shift.assignment.wizard'
    _description = 'Wizard gan ca nhan vien'

    department_id = fields.Many2one('phong_ban', string='Phòng ban')
    only_without_shift = fields.Boolean(
        string='Chỉ nhân viên chưa gán ca',
        default=True,
    )
    employee_ids = fields.Many2many(
        'nhan_vien',
        'shift_assignment_wizard_nhan_vien_rel',
        'wizard_id',
        'employee_id',
        string='Nhân viên áp dụng',
    )
    shift_id = fields.Many2one(
        'attendance.rule',
        string='Ca làm việc',
        required=True,
        domain=[('active', '=', True)],
    )

    def _build_employee_domain(self):
        self.ensure_one()
        domain = []
        if self.department_id:
            domain.append(('phong_ban_id', '=', self.department_id.id))
        if self.only_without_shift:
            domain.append(('shift_id', '=', False))
        return domain

    @api.onchange('department_id', 'only_without_shift')
    def _onchange_employee_domain(self):
        domain = self._build_employee_domain()
        self.employee_ids = self.employee_ids.filtered_domain(domain)
        return {'domain': {'employee_ids': domain}}

    def action_assign_shift(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_('Vui lòng chọn ít nhất một nhân viên để gán ca.'))

        self.employee_ids.write({'shift_id': self.shift_id.id})

        linked_hr_employees = self.env['hr.employee'].search([
            ('nhan_vien_id', 'in', self.employee_ids.ids)
        ])
        if linked_hr_employees:
            linked_hr_employees.write({'shift_id': self.shift_id.id})

        return {'type': 'ir.actions.act_window_close'}