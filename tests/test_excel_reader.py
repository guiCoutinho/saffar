"""Testes de app.core.excel_reader (render de mensagem, unidades, parsing)."""
import os
import tempfile
import unittest

import pandas as pd

from app.core.excel_reader import (
    render_message,
    normalize_unidade,
    parse_inadimplentes,
)


class RenderMessageTest(unittest.TestCase):
    def test_substituicao_basica(self):
        self.assertEqual(
            render_message("Olá {{nome}}, tudo bem?", {"nome": "João"}),
            "Olá João, tudo bem?",
        )

    def test_placeholder_desconhecido_permanece(self):
        self.assertEqual(render_message("Oi {{x}}", {"nome": "João"}), "Oi {{x}}")

    def test_valor_none_vira_string_vazia(self):
        self.assertEqual(render_message("[{{nome}}]", {"nome": None}), "[]")

    def test_nao_re_substitui_valor_que_parece_placeholder(self):
        # 'a' contém literalmente '{{b}}'; passo único NÃO deve trocá-lo por 'HACK'.
        row = {"a": "{{b}}", "b": "HACK"}
        self.assertEqual(render_message("{{a}}", row), "{{b}}")

    def test_multiplos_campos(self):
        row = {"nome": "Ana", "unidade": "A-302"}
        self.assertEqual(
            render_message("{{nome}} - unidade {{unidade}}", row),
            "Ana - unidade A-302",
        )


class NormalizeUnidadeTest(unittest.TestCase):
    def test_espacos_e_separadores(self):
        self.assertEqual(normalize_unidade("a - 0302"), "A302")

    def test_traco_interno(self):
        self.assertEqual(normalize_unidade("A-302"), "A302")

    def test_sufixo(self):
        self.assertEqual(normalize_unidade("302-B"), "302B")

    def test_zeros_a_esquerda(self):
        self.assertEqual(normalize_unidade("0010"), "10")

    def test_apenas_zeros(self):
        self.assertEqual(normalize_unidade("000"), "0")


class ParseInadimplentesTest(unittest.TestCase):
    def _write_xlsx(self, rows):
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        pd.DataFrame(rows).to_excel(path, header=False, index=False)
        self.addCleanup(lambda: os.remove(path))
        return path

    def test_parse_basico(self):
        path = self._write_xlsx([
            ["302 - João Silva", "", ""],
            ["Competência", "Valor", "Total"],
            ["01/2024", "100", ""],
            ["02/2024", "150", ""],
            ["Total", "", "250"],
            ["A-303 - Maria", "", ""],
            ["Competência", "Valor", "Total"],
            ["03/2024", "300", ""],
            ["Total", "", "300"],
        ])
        result = parse_inadimplentes(path)

        self.assertEqual(set(result), {"302", "A303"})
        self.assertEqual(result["302"].competencias, ["01/2024", "02/2024"])
        self.assertEqual(result["302"].total, "250")
        self.assertEqual(result["A303"].competencias, ["03/2024"])
        self.assertEqual(result["A303"].total, "300")

    def test_parse_unidade_com_espacos(self):
        # Unidades com bloco/espaços, ex.: "08 B Escandinavia".
        path = self._write_xlsx([
            ["08 B Escandinavia - João Silva", "", ""],
            ["Competência", "Valor", "Total"],
            ["01/2024", "100", ""],
            ["Total", "", "100"],
            ["12 A Nórdico - Maria", "", ""],
            ["Competência", "Valor", "Total"],
            ["02/2024", "200", ""],
            ["Total", "", "200"],
        ])
        result = parse_inadimplentes(path)

        # normalize_unidade remove espaços e zeros à esquerda: "08 B Escandinavia" -> "8BESCANDINAVIA"
        self.assertEqual(set(result), {"8BESCANDINAVIA", "12ANORDICO"})
        self.assertEqual(result["8BESCANDINAVIA"].competencias, ["01/2024"])
        self.assertEqual(result["8BESCANDINAVIA"].total, "100")
        self.assertEqual(result["12ANORDICO"].total, "200")

    def test_unidade_com_espacos_bate_com_contato(self):
        # A unidade do relatório e a do cadastro normalizam para o mesmo valor,
        # independentemente de espaços, zeros à esquerda e maiúsculas/minúsculas.
        self.assertEqual(
            normalize_unidade("08 B Escandinavia"),
            normalize_unidade("8 b escandinavia"),
        )

    def test_titulo_sem_digito_nao_e_unidade(self):
        # Linha de título (sem dígito antes do traço) não deve virar unidade.
        path = self._write_xlsx([
            ["Relatório de Inadimplência - Condomínio", "", ""],
            ["302 - João", "", ""],
            ["Competência", "Valor", "Total"],
            ["01/2024", "100", ""],
            ["Total", "", "100"],
        ])
        result = parse_inadimplentes(path)
        self.assertEqual(set(result), {"302"})

    def test_arquivo_vazio(self):
        path = self._write_xlsx([])
        with self.assertRaises(ValueError):
            parse_inadimplentes(path)


if __name__ == "__main__":
    unittest.main()
