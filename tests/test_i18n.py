import unittest

from openremouse import actions, dialogs, i18n


class I18nTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("fr", save=False)

    def test_all_registry_texts_are_translated(self):
        missing = set()
        for spec in actions.REGISTRY.values():
            for text in [spec.label, spec.category] + [f.label for f in spec.fields]:
                if text not in i18n.EN:
                    missing.add(text)
        for cat, items in dialogs.MENU:
            for text in [cat] + [label for label, _ in items]:
                if text not in i18n.EN:
                    missing.add(text)
        missing.discard("X"); missing.discard("Y"); missing.discard("OpenReMouse")
        self.assertEqual(sorted(missing), [])

    def test_tr(self):
        i18n.set_lang("en", save=False)
        self.assertEqual(i18n.tr("Annuler"), "Cancel")
        self.assertEqual(i18n.tr("Terminé : %s", "m"), "Finished: m")
        self.assertEqual(i18n.tr("texte sans traduction"), "texte sans traduction")
        i18n.set_lang("fr", save=False)
        self.assertEqual(i18n.tr("Annuler"), "Annuler")

    def test_format_placeholders_match(self):
        import re
        for fr, en in i18n.EN.items():
            self.assertEqual(sorted(re.findall(r"%[sdr]", fr)), sorted(re.findall(r"%[sdr]", en)), fr)


if __name__ == "__main__":
    unittest.main()
