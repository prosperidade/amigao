"""Fechamento comercial (Incremento 5, ADR-074): Redator pré-contratação e Orçamento da Rota."""


class ComercialError(ValueError):
    """Geração recusada com motivo honesto. A API traduz em 422; a cadeia, em passo falho
    que a retomada reexecuta."""
