"""Testes de app.core.phone_utils (lógica pura de normalização de telefone)."""
import unittest

from app.core.phone_utils import normalize_phone, to_wa_phone, split_phones


class NormalizePhoneTest(unittest.TestCase):
    def test_internacional_com_simbolos(self):
        self.assertEqual(normalize_phone("+55 32 99999-8888"), "32999998888")

    def test_zero_de_operadora(self):
        self.assertEqual(normalize_phone("032 99999-8888"), "32999998888")

    def test_celular_sem_ddd_recebe_ddd_padrao(self):
        self.assertEqual(normalize_phone("99999-8888"), "32999998888")

    def test_fixo_sem_ddd_recebe_ddd_padrao(self):
        # 8 dígitos (fixo sem DDD) -> ganha o DDD padrão 32 -> 10 dígitos.
        self.assertEqual(normalize_phone("3334-4444"), "3233344444")

    def test_ja_normalizado_permanece(self):
        self.assertEqual(normalize_phone("3299998888"), "3299998888")

    def test_ddd_55_local_nao_e_confundido_com_codigo_do_pais(self):
        # DDD 55 (Santa Maria/RS) com 9 dígitos: 11 no total, não deve perder o "55".
        self.assertEqual(normalize_phone("55999998888"), "55999998888")

    def test_pais_mais_ddd_55(self):
        # 55 (país) + 55 (DDD) + 9 dígitos = 13 -> remove só o código do país.
        self.assertEqual(normalize_phone("5555999998888"), "55999998888")

    def test_mesma_chave_para_formatos_diferentes(self):
        alvo = normalize_phone("+55 (32) 99999-8888")
        self.assertEqual(normalize_phone("03299999-8888"), alvo)
        self.assertEqual(normalize_phone("99999 8888"), alvo)


class ToWaPhoneTest(unittest.TestCase):
    def test_celular_11_digitos(self):
        self.assertEqual(to_wa_phone("32999998888"), "5532999998888")

    def test_fixo_10_digitos(self):
        self.assertEqual(to_wa_phone("3233334444"), "553233334444")

    def test_com_ruido(self):
        self.assertEqual(to_wa_phone("+55 32 99999-8888"), "5532999998888")


class SplitPhonesTest(unittest.TestCase):
    def test_ponto_e_virgula_e_virgula(self):
        self.assertEqual(split_phones("111 ; 222 , 333"), ["111", "222", "333"])

    def test_vazio(self):
        self.assertEqual(split_phones("   "), [])

    def test_unico(self):
        self.assertEqual(split_phones("32999998888"), ["32999998888"])


if __name__ == "__main__":
    unittest.main()
