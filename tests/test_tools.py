"""Testes das ferramentas de domínio."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from gestlog.tools.inventory import (
    build_inventory_tools,
    calcular_reposicao,
    consultar_estoque,
    listar_movimentacoes,
)
from gestlog.tools.suppliers import (
    avaliar_desempenho,
    build_supplier_tools,
    consultar_fornecedor,
    listar_fornecedores,
)
from gestlog.tools.transport import (
    build_transport_tools,
    calcular_frete,
    consultar_prazo,
    rastrear_entrega,
)


class _FakeRepo:
    """Repositório fake com itens por empresa para exercitar as tools."""

    def __init__(self, itens_por_empresa: dict[UUID, list[SimpleNamespace]]) -> None:
        self._itens = itens_por_empresa

    def get_by_sku(self, empresa_id: UUID, sku: str) -> SimpleNamespace | None:
        for item in self._itens.get(empresa_id, []):
            if item.sku == sku:
                return item
        return None

    def list(self, empresa_id: UUID) -> list[SimpleNamespace]:
        return list(self._itens.get(empresa_id, []))


class _FakeSupplierRepo:
    """Repositório fake de fornecedores por empresa."""

    def __init__(self, itens_por_empresa: dict[UUID, list[SimpleNamespace]]) -> None:
        self._itens = itens_por_empresa

    def get_by_fornecedor_id(
        self, empresa_id: UUID, fornecedor_id: str
    ) -> SimpleNamespace | None:
        for item in self._itens.get(empresa_id, []):
            if item.fornecedor_id == fornecedor_id:
                return item
        return None

    def list(self, empresa_id: UUID) -> list[SimpleNamespace]:
        return list(self._itens.get(empresa_id, []))


class _FakeTransportRepo:
    """Repositório fake de registros de transporte por empresa."""

    def __init__(self, itens_por_empresa: dict[UUID, list[SimpleNamespace]]) -> None:
        self._itens = itens_por_empresa

    def get_by_codigo(self, empresa_id: UUID, codigo: str) -> SimpleNamespace | None:
        for item in self._itens.get(empresa_id, []):
            if item.codigo_rastreio == codigo:
                return item
        return None

    def list(self, empresa_id: UUID) -> list[SimpleNamespace]:
        return list(self._itens.get(empresa_id, []))


def _item(sku: str, quantidade: int, minimo: int, local: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        sku=sku, nome=f"Item {sku}", quantidade=quantidade, minimo=minimo, local=local
    )


def _fornecedor(
    fid: str,
    categoria: str = "insumos",
    prazo_dias: int = 5,
    avaliacao: float = 4.5,
    ativo: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        fornecedor_id=fid,
        nome=f"Fornecedor {fid}",
        categoria=categoria,
        prazo_dias=prazo_dias,
        avaliacao=avaliacao,
        ativo=ativo,
    )


def _registro(
    codigo: str,
    origem: str = "Sao Paulo",
    destino: str = "Curitiba",
    status: str = "em trânsito",
) -> SimpleNamespace:
    return SimpleNamespace(
        codigo_rastreio=codigo, origem=origem, destino=destino, status=status
    )


def _transport_repo() -> tuple[UUID, UUID, _FakeTransportRepo]:
    empresa = uuid4()
    outra = uuid4()
    repo = _FakeTransportRepo(
        {
            empresa: [
                _registro("GL-1", status="em trânsito"),
                _registro("GL-2", status="entregue"),
                _registro("GL-3", status="atrasado"),
            ],
            outra: [_registro("GL-1", status="entregue")],
        }
    )
    return empresa, outra, repo


def _repo_a() -> tuple[UUID, UUID, _FakeRepo]:
    empresa = uuid4()
    outra = uuid4()
    repo = _FakeRepo(
        {
            empresa: [_item("SKU-1", 120, 50, "A1"), _item("SKU-2", 20, 40, "B3")],
            outra: [_item("SKU-1", 500, 10, "X9")],
        }
    )
    return empresa, outra, repo


def _supplier_repo() -> tuple[UUID, UUID, _FakeSupplierRepo]:
    empresa = uuid4()
    outra = uuid4()
    repo = _FakeSupplierRepo(
        {
            empresa: [
                _fornecedor("F-1"),
                _fornecedor("F-2", prazo_dias=20, avaliacao=3.0),
                _fornecedor("F-3", categoria="transporte", ativo=False),
            ],
            outra: [_fornecedor("F-1", avaliacao=1.0, prazo_dias=40)],
        }
    )
    return empresa, outra, repo


def test_transport_tools() -> None:
    frete = calcular_frete.invoke(
        {"origem": "Sao Paulo", "destino": "Curitiba", "peso_kg": 10.0}
    )
    assert "R$" in frete
    assert "Prazo" in consultar_prazo.invoke(
        {"origem": "Sao Paulo", "destino": "Salvador"}
    )
    assert "GL-1001" in rastrear_entrega.invoke({"codigo": "GL-1001"})
    assert "não encontrado" in rastrear_entrega.invoke({"codigo": "XXX"})
    mesma_cidade = calcular_frete.invoke(
        {"origem": "Salvador", "destino": "salvador", "peso_kg": 0.0}
    )
    assert "0 km" in mesma_cidade


def test_supplier_tools() -> None:
    assert "TransLog" in listar_fornecedores.invoke({"categoria": "transporte"})
    assert "Nenhum" in listar_fornecedores.invoke({"categoria": "inexistente"})
    assert "ativo" in consultar_fornecedor.invoke({"fornecedor_id": "F-001"})
    assert "não encontrado" in consultar_fornecedor.invoke({"fornecedor_id": "F-999"})
    assert "atrasos" in avaliar_desempenho.invoke({"fornecedor_id": "F-002"})
    assert "não encontrado" in avaliar_desempenho.invoke({"fornecedor_id": "F-999"})


def test_inventory_tools() -> None:
    assert "SKU-100" in consultar_estoque.invoke({"sku": "sku-100"})
    assert "não encontrado" in consultar_estoque.invoke({"sku": "SKU-999"})
    assert "reposição sugerida" in calcular_reposicao.invoke(
        {"sku": "SKU-200", "consumo_medio_dia": 10}
    )
    assert "maior que zero" in calcular_reposicao.invoke(
        {"sku": "SKU-200", "consumo_medio_dia": 0}
    )
    assert "não encontrado" in calcular_reposicao.invoke(
        {"sku": "SKU-999", "consumo_medio_dia": 5}
    )
    assert "SKU-300" in listar_movimentacoes.invoke({"sku": "SKU-300"})
    assert "não encontrado" in listar_movimentacoes.invoke({"sku": "SKU-999"})


def test_inventory_factory_consulta_por_tenant() -> None:
    empresa, _, repo = _repo_a()
    consultar, *_ = build_inventory_tools(repo, empresa)

    assert "SKU-1" in consultar.invoke({"sku": "sku-1"})
    assert "não encontrado" in consultar.invoke({"sku": "SKU-999"})


def test_inventory_factory_isolamento_entre_empresas() -> None:
    empresa, outra, repo = _repo_a()
    tools = {tool.name: tool for tool in build_inventory_tools(repo, empresa)}

    assert "quantidade 120" in tools["consultar_estoque"].invoke({"sku": "SKU-1"})
    assert repo.get_by_sku(outra, "SKU-1").quantidade == 500


def test_inventory_factory_reposicao() -> None:
    empresa, _, repo = _repo_a()
    tools = {tool.name: tool for tool in build_inventory_tools(repo, empresa)}

    assert "reposição sugerida" in tools["calcular_reposicao"].invoke(
        {"sku": "SKU-1", "consumo_medio_dia": 5}
    )
    assert "maior que zero" in tools["calcular_reposicao"].invoke(
        {"sku": "SKU-1", "consumo_medio_dia": 0}
    )
    assert "não encontrado" in tools["calcular_reposicao"].invoke(
        {"sku": "SKU-999", "consumo_medio_dia": 5}
    )


def test_inventory_factory_movimentacoes() -> None:
    empresa, _, repo = _repo_a()
    tools = {tool.name: tool for tool in build_inventory_tools(repo, empresa)}

    assert "SKU-1" in tools["listar_movimentacoes"].invoke({"sku": "SKU-1"})
    assert "não encontrado" in tools["listar_movimentacoes"].invoke({"sku": "SKU-999"})


def test_inventory_factory_prever_demanda() -> None:
    empresa, _, repo = _repo_a()
    tools = {tool.name: tool for tool in build_inventory_tools(repo, empresa)}

    assert "demanda projetada" in tools["prever_demanda"].invoke(
        {"sku": "SKU-1", "consumo_medio_dia": 10}
    )
    assert "maior que zero" in tools["prever_demanda"].invoke(
        {"sku": "SKU-1", "consumo_medio_dia": 0}
    )
    assert "não encontrado" in tools["prever_demanda"].invoke(
        {"sku": "SKU-999", "consumo_medio_dia": 10}
    )


def test_inventory_factory_otimizar_armazem() -> None:
    empresa, _, repo = _repo_a()
    tools = {tool.name: tool for tool in build_inventory_tools(repo, empresa)}

    saida = tools["otimizar_armazem"].invoke({})
    assert "SKU-2" in saida and "abaixo do mínimo" in saida
    vazio = _FakeRepo({empresa: []})
    tools_vazio = {t.name: t for t in build_inventory_tools(vazio, empresa)}
    assert "Nenhum SKU abaixo" in tools_vazio["otimizar_armazem"].invoke({})


def test_inventory_factory_otimizar_custos() -> None:
    empresa, _, repo = _repo_a()
    tools = {tool.name: tool for tool in build_inventory_tools(repo, empresa)}

    saida = tools["otimizar_custos"].invoke({})
    assert "SKU-1" in saida and "excedente" in saida
    vazio = _FakeRepo({empresa: []})
    tools_vazio = {t.name: t for t in build_inventory_tools(vazio, empresa)}
    assert "Nenhum SKU" in tools_vazio["otimizar_custos"].invoke({})


def test_supplier_factory_consulta_por_tenant() -> None:
    empresa, _, repo = _supplier_repo()
    tools = {tool.name: tool for tool in build_supplier_tools(repo, empresa)}

    assert "F-1" in tools["consultar_fornecedor"].invoke({"fornecedor_id": "f-1"})
    assert "não encontrado" in tools["consultar_fornecedor"].invoke(
        {"fornecedor_id": "F-999"}
    )


def test_supplier_factory_isolamento_entre_empresas() -> None:
    empresa, outra, repo = _supplier_repo()
    tools = {tool.name: tool for tool in build_supplier_tools(repo, empresa)}

    assert "nota 4.5" in tools["consultar_fornecedor"].invoke({"fornecedor_id": "F-1"})
    assert repo.get_by_fornecedor_id(outra, "F-1").avaliacao == 1.0


def test_supplier_factory_listar_fornecedores() -> None:
    empresa, _, repo = _supplier_repo()
    tools = {tool.name: tool for tool in build_supplier_tools(repo, empresa)}

    insumos = tools["listar_fornecedores"].invoke({"categoria": "insumos"})
    assert "F-1" in insumos and "F-2" in insumos and "F-3" not in insumos
    assert "Nenhum" in tools["listar_fornecedores"].invoke({"categoria": "inexistente"})


def test_supplier_factory_avaliar_desempenho() -> None:
    empresa, _, repo = _supplier_repo()
    tools = {tool.name: tool for tool in build_supplier_tools(repo, empresa)}

    saida = tools["avaliar_desempenho"].invoke({"fornecedor_id": "F-1"})
    assert "nota 4.5" in saida and "prazo médio 5 dia(s)" in saida
    assert "não encontrado" in tools["avaliar_desempenho"].invoke(
        {"fornecedor_id": "F-999"}
    )


def test_supplier_factory_tratar_conformidade() -> None:
    empresa, _, repo = _supplier_repo()
    tools = {tool.name: tool for tool in build_supplier_tools(repo, empresa)}

    saida = tools["tratar_conformidade"].invoke({})
    assert "F-2" in saida and "F-3" in saida and "F-1" not in saida
    assert "inativo" in saida and "abaixo de" in saida and "acima de" in saida

    conformes = _FakeSupplierRepo({empresa: [_fornecedor("F-9")]})
    tools_ok = {t.name: t for t in build_supplier_tools(conformes, empresa)}
    assert "Todos os fornecedores em conformidade" in tools_ok[
        "tratar_conformidade"
    ].invoke({})

    vazio = _FakeSupplierRepo({empresa: []})
    tools_vazio = {t.name: t for t in build_supplier_tools(vazio, empresa)}
    assert "Nenhum fornecedor cadastrado" in tools_vazio["tratar_conformidade"].invoke(
        {}
    )


def test_supplier_factory_conformidade_limites() -> None:
    empresa = uuid4()
    limites = _FakeSupplierRepo(
        {
            empresa: [
                _fornecedor("F-4.0", avaliacao=4.0, prazo_dias=15),
                _fornecedor("F-3.9", avaliacao=3.9, prazo_dias=15),
                _fornecedor("F-16", avaliacao=4.0, prazo_dias=16),
            ]
        }
    )
    tools = {t.name: t for t in build_supplier_tools(limites, empresa)}
    saida = tools["tratar_conformidade"].invoke({})

    assert "F-4.0" not in saida
    assert "F-3.9" in saida and "F-16" in saida


def test_transport_factory_rastrear_por_tenant() -> None:
    empresa, _, repo = _transport_repo()
    tools = {tool.name: tool for tool in build_transport_tools(repo, empresa)}

    assert "em trânsito" in tools["rastrear_entrega"].invoke({"codigo": "gl-1"})
    assert "não encontrado" in tools["rastrear_entrega"].invoke({"codigo": "GL-999"})


def test_transport_factory_isolamento_entre_empresas() -> None:
    empresa, outra, repo = _transport_repo()
    tools = {tool.name: tool for tool in build_transport_tools(repo, empresa)}
    tools_outra = {tool.name: tool for tool in build_transport_tools(repo, outra)}

    assert "em trânsito" in tools["rastrear_entrega"].invoke({"codigo": "GL-1"})
    assert "entregue" in tools_outra["rastrear_entrega"].invoke({"codigo": "GL-1"})


def test_transport_factory_otimizar_entrega() -> None:
    empresa, _, repo = _transport_repo()
    tools = {tool.name: tool for tool in build_transport_tools(repo, empresa)}

    saida = tools["otimizar_entrega"].invoke({})
    assert "GL-1" in saida and "GL-3" in saida and "GL-2" not in saida

    sem_pendencia = _FakeTransportRepo(
        {empresa: [_registro("GL-9", status="entregue")]}
    )
    tools_ok = {t.name: t for t in build_transport_tools(sem_pendencia, empresa)}
    assert "Nenhuma entrega pendente" in tools_ok["otimizar_entrega"].invoke({})

    vazio = _FakeTransportRepo({empresa: []})
    tools_vazio = {t.name: t for t in build_transport_tools(vazio, empresa)}
    assert "Nenhuma entrega registrada" in tools_vazio["otimizar_entrega"].invoke({})


def test_transport_factory_mantem_calculo() -> None:
    empresa, _, repo = _transport_repo()
    tools = {tool.name: tool for tool in build_transport_tools(repo, empresa)}

    frete = tools["calcular_frete"].invoke(
        {"origem": "Sao Paulo", "destino": "Curitiba", "peso_kg": 10.0}
    )
    assert "R$" in frete and "408 km" in frete
    assert "Prazo" in tools["consultar_prazo"].invoke(
        {"origem": "Sao Paulo", "destino": "Salvador"}
    )
