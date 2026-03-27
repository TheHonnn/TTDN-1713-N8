{
    'name': 'Nhân sự AI - Chấm công',
    'version': '1.0.0',
    'summary': 'Xử lý sự kiện chấm công AI và đồng bộ hr.attendance',
    'author': 'TTDN Team',
    'depends': ['base', 'web', 'hr', 'hr_attendance', 'nhan_su'],
    'data': [
        'security/ir.model.access.csv',
        'views/nhan_vien_views.xml',
        'views/ai_attendance_event_views.xml',
        'views/menu.xml',
    ],
    'external_dependencies': {
        'python': ['face_recognition', 'numpy', 'PIL'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}