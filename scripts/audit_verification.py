"""Validate optional per-matter source verification records, not their legal truth."""
from datetime import date
from urllib.parse import urlsplit


def audit_verification(authorities):
    errors, gaps = [], []
    for index, row in enumerate(authorities, 1):
        if not isinstance(row, dict) or 'verification' not in row:
            continue  # Legacy records are not upgraded to current verification.
        label = f'authorities第{index}项.verification'
        value = row['verification']
        if not isinstance(value, dict):
            errors.append(f'{label}必须为对象')
            continue
        if value.get('status') not in ('checked', 'snapshot', 'unavailable', 'conflict'):
            errors.append(f'{label}.status无效')
            continue
        if value['status'] != 'checked':
            gaps.append(f'{label}本次核验尚未完成')
            continue
        for key in ('verifiedAt', 'url', 'readScope', 'version', 'effectiveFrom', 'applicability'):
            text = value.get(key)
            if not isinstance(text, str) or not text.strip() or text.strip().lower() in ('待核', '待确认', 'unknown', 'pending'):
                gaps.append(f'{label}.{key}未完成，不能视为已核验')
        for key in ('verifiedAt', 'effectiveFrom'):
            try:
                text = value.get(key)
                if not isinstance(text, str) or date.fromisoformat(text).isoformat() != text:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(f'{label}.{key}须为有效YYYY-MM-DD日期')
        try:
            parsed = urlsplit(value.get('url', ''))
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError
            parsed.port
        except (ValueError, TypeError, AttributeError):
            errors.append(f'{label}.url须为无凭证HTTPS来源地址')
    return errors, gaps
