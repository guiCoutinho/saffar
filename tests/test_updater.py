"""Testes de app.core.updater (comparação de versões, contexto SSL)."""
import ssl
import unittest

from app.core.updater import _version_tuple, _ssl_context


class VersionTupleTest(unittest.TestCase):
    def test_tag_com_prefixo_v(self):
        self.assertEqual(_version_tuple("v1.2.3"), (1, 2, 3))

    def test_sem_prefixo(self):
        self.assertEqual(_version_tuple("1.2.3"), (1, 2, 3))

    def test_completa_com_zeros(self):
        # 'v1.2' precisa virar (1, 2, 0) e não (1, 2) para não comparar tuplas
        # de tamanhos diferentes (causaria atualização indevida).
        self.assertEqual(_version_tuple("v1.2"), (1, 2, 0))
        self.assertEqual(_version_tuple("v2"), (2, 0, 0))

    def test_ordem_de_comparacao(self):
        self.assertLess(_version_tuple("1.2.3"), _version_tuple("1.2.4"))
        self.assertLess(_version_tuple("1.2.0"), _version_tuple("1.10.0"))
        self.assertLessEqual(_version_tuple("1.2"), _version_tuple("1.2.0"))
        self.assertGreater(_version_tuple("v2.0.0"), _version_tuple("v1.9.9"))


class SSLContextTest(unittest.TestCase):
    def test_retorna_contexto_ssl(self):
        # Deve devolver um SSLContext válido (truststore/certifi/padrão), nunca
        # levantar — é o que garante que a verificação TLS do updater tenha CAs.
        ctx = _ssl_context()
        self.assertIsInstance(ctx, ssl.SSLContext)

    def test_contexto_e_cacheado(self):
        self.assertIs(_ssl_context(), _ssl_context())


if __name__ == "__main__":
    unittest.main()
