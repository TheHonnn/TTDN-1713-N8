from odoo import fields, models
from odoo.exceptions import UserError


class NhanSuAiChatQuickAskWizard(models.TransientModel):
    _name = 'nhan_su.ai.chat.quick.ask.wizard'
    _description = 'Hỏi nhanh Chat AI Nhân sự'

    chat_id = fields.Many2one('nhan_su.ai.chat', string='Cuộc trò chuyện', required=True)
    question = fields.Char(
        string='Câu hỏi',
        required=True,
        help='Nhập câu hỏi và bấm Gửi, không cần mở chế độ chỉnh sửa form chính.',
    )

    def action_send_question(self):
        self.ensure_one()
        if not self.chat_id:
            raise UserError('Không tìm thấy cuộc trò chuyện để gửi câu hỏi.')

        self.chat_id._ask_with_question(self.question)
        return {'type': 'ir.actions.act_window_close'}


class NhanSuAiChatApiConfigWizard(models.TransientModel):
    _name = 'nhan_su.ai.chat.api.config.wizard'
    _description = 'Cấu hình API Chat AI Nhân sự'

    api_url = fields.Char(string='AI API URL')
    api_key = fields.Char(string='AI API Key')
    ai_model = fields.Char(string='Model AI', default='gpt-4o-mini')

    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        config = self.env['ir.config_parameter'].sudo()
        values.update({
            'api_url': config.get_param('attendance_policy.ai_api_url') or '',
            'api_key': config.get_param('attendance_policy.ai_api_key') or '',
            'ai_model': config.get_param('attendance_policy.ai_model') or 'gpt-4o-mini',
        })
        return values

    def action_save_api_config(self):
        self.ensure_one()
        config = self.env['ir.config_parameter'].sudo()
        config.set_param('attendance_policy.ai_api_url', (self.api_url or '').strip())
        config.set_param('attendance_policy.ai_api_key', (self.api_key or '').strip())
        config.set_param('attendance_policy.ai_model', (self.ai_model or '').strip() or 'gpt-4o-mini')
        return {'type': 'ir.actions.act_window_close'}
