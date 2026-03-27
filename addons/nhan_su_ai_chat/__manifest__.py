{
    'name': 'Trợ lý AI Nhân sự',
    'version': '1.0',
    'summary': 'Chat AI hỏi đáp về dữ liệu nhân sự công ty',
    'author': 'TTDN Team',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'nhan_su',
        'nhan_su_attendance_policy',
        'nhan_su_attendance_ai',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_company_chat_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
