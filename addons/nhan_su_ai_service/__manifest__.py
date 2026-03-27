{
    'name': 'Nhân sự AI - Nền tảng API',
    'version': '1.0.0',
    'category': 'Human Resources',
    'summary': 'Core API layer for Face Attendance AI System',
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'license': 'LGPL-3',
    
    'depends': [
        'base',
        'web',
        'hr',
        'nhan_su',
    ],
    
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',
    ],
    
    'external_dependencies': {
        'python': [
            'requests',
            'python-json-logger',
        ],
    },
    
    'installable': True,
    'auto_install': False,
    'application': True,
}
