from datetime import date

from legal_export_service import MatterIntake, follow_up_ids


def test_undelivered_signed_document_is_flagged_after_deadline():
    matters = [
        MatterIntake("M-1", "Acme", "signed.pdf", date(2026, 9, 1), False),
        MatterIntake("M-2", "Beta", "signed.pdf", date(2026, 9, 1), True),
        MatterIntake("M-3", "Gamma", "signed.pdf", date(2026, 9, 20), False),
    ]
    assert follow_up_ids(matters, date(2026, 9, 12)) == ["M-1"]


def test_export_cleans_up_on_success_and_generation_failure():
    from infrai_client import InfraiError, StoragePaths
    from legal_export_service import export_matters
    import pytest

    for fail_pdf in (False, True):
        class Client:
            deleted = False
            calls = []

            def request(self, method, path, body=None):
                self.calls.append((method, path))
                if path == '/v1/pdf/generate':
                    assert body['store'] is False
                    if fail_pdf:
                        raise ValueError('render failed')
                if method == 'DELETE' and '/bucket/' in path:
                    self.deleted = True
                if '/object/list/' in path:
                    if self.deleted:
                        raise InfraiError('NOT_FOUND', {}, 404)
                    return []
                if '/presign/' in path:
                    return {'url': 'https://example.invalid/download'}
                return {}

        client = Client()
        if fail_pdf:
            with pytest.raises(ValueError, match='render failed'):
                export_matters(client, StoragePaths('unique-bucket', 'unique.csv'), [], date.today())
        else:
            export_matters(client, StoragePaths('unique-bucket', 'unique.csv'), [], date.today())
        assert client.calls[-4:] == [
            ('DELETE', '/v1/storage/object/delete/unique-bucket/unique.csv'),
            ('GET', '/v1/storage/object/list/unique-bucket'),
            ('DELETE', '/v1/storage/bucket/delete/unique-bucket'),
            ('GET', '/v1/storage/object/list/unique-bucket'),
        ]
