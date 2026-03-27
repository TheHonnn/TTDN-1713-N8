{
    'name': 'Nhân sự - Lương theo chức vụ',
    'version': '1.0.0',
    'summary': 'Tính lương, thưởng, phạt theo chức vụ và bảng công ngày',
    'author': 'TTDN Team',
    'depends': ['mail', 'nhan_su', 'nhan_su_attendance_policy'],
    'external_dependencies': {
        'python': ['reportlab'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/payroll_cron.xml',
        'report/payroll_reports.xml',
        'views/payroll_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}