import unittest

from verify_release_privacy import artifact_errors


class ReleasePrivacyTests(unittest.TestCase):
    def test_codeview_profile_path(self):
        self.assertIn('personal-profile-path', artifact_errors(
            'plugin.dll', b'RSDS\x00C:\\Users\\test-profile\\project\\plugin.pdb\x00'))

    def test_utf16_profile_path_both_alignments(self):
        text = 'C:\\Users\\test-profile\\project'
        for prefix in (b'', b'X'):
            self.assertIn('personal-profile-path', artifact_errors(
                'plugin.dll', prefix + text.encode('utf-16le')))

    def test_escaped_json_path(self):
        self.assertIn('personal-profile-path', artifact_errors(
            'report.json', br'{"path":"C:\\Users\\test-profile\\project"}'))

    def test_portable_path_allowed(self):
        self.assertEqual([], artifact_errors('plugin.dll', b'/_/PurgatoryRu/Plugin.cs\x00'))

    def test_symbols_rejected(self):
        self.assertIn('private-key-or-symbol-file', artifact_errors('plugin.pdb', b'BSJB'))

    def test_private_key_rejected(self):
        self.assertIn('private-key-header', artifact_errors(
            'unexpected.txt', b'-----BEGIN PRIVATE KEY-----'))


if __name__ == '__main__':
    unittest.main()
