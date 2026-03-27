import re
import unicodedata

from odoo import api, fields, models

class ChucVu(models.Model):
    _name = 'chuc_vu'
    _description = 'Bảng chứa thông tin chức vụ'
    _rec_name = 'ten_chuc_vu'

    ma_chuc_vu = fields.Char("Mã chức vụ")
    ten_chuc_vu = fields.Char("Tên chức vụ", required=True)

    _sql_constraints = [
        ('chuc_vu_code_unique', 'unique(ma_chuc_vu)', 'Mã chức vụ đã tồn tại.'),
    ]

    @api.onchange('ten_chuc_vu')
    def _onchange_ten_chuc_vu(self):
        for record in self:
            if record.ten_chuc_vu and not record.ma_chuc_vu:
                record.ma_chuc_vu = record._generate_job_code(record.ten_chuc_vu)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ten_chuc_vu') and not vals.get('ma_chuc_vu'):
                vals['ma_chuc_vu'] = self._generate_job_code(vals['ten_chuc_vu'])
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            update_vals = dict(vals)
            if update_vals.get('ten_chuc_vu') and not update_vals.get('ma_chuc_vu') and not record.ma_chuc_vu:
                update_vals['ma_chuc_vu'] = record._generate_job_code(update_vals['ten_chuc_vu'], exclude_id=record.id)
            super(ChucVu, record).write(update_vals)
        return True

    def _generate_job_code(self, job_name, exclude_id=None):
        base_code = self._build_base_code(job_name)
        return self._make_unique_code(base_code, exclude_id=exclude_id)

    def _build_base_code(self, job_name):
        original_tokens = [token for token in re.split(r'[^\w]+', job_name or '') if token]
        normalized_tokens = [self._strip_accents(token) for token in original_tokens]

        code_parts = []
        for original_token, normalized_token in zip(original_tokens, normalized_tokens):
            if not normalized_token:
                continue
            if original_token.isupper() and len(normalized_token) <= 4:
                code_parts.append(normalized_token.upper())
            else:
                code_parts.append(normalized_token[0].upper())

        return ''.join(code_parts) or 'CV'

    def _make_unique_code(self, base_code, exclude_id=None):
        ChucVu = self.env['chuc_vu'].sudo()
        sequence = 1

        while True:
            candidate = f"{base_code} {sequence:02d}"
            domain = [('ma_chuc_vu', '=', candidate)]
            if exclude_id:
                domain.append(('id', '!=', exclude_id))
            if not ChucVu.search_count(domain):
                return candidate
            sequence += 1

    @staticmethod
    def _strip_accents(value):
        normalized = unicodedata.normalize('NFD', value or '')
        return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')