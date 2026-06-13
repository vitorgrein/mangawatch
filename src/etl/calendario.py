"""Calendário de dias úteis (feriados nacionais BR + extras do settings.yml).

Regra da empresa: o processo roda sempre para o último dia útil, e eventos de
fim de semana/feriado acumulam no dia útil ANTERIOR. Assim, a janela de um
data_ref vai de data_ref até o dia anterior ao próximo dia útil.
"""

from __future__ import annotations

from datetime import date, timedelta

import holidays as _holidays


class CalendarioUtil:
    def __init__(self, feriados_extras: list[date] | None = None) -> None:
        self._extras = set(feriados_extras or [])
        self._br: dict[int, set[date]] = {}

    def _feriados(self, ano: int) -> set[date]:
        if ano not in self._br:
            self._br[ano] = set(_holidays.Brazil(years=ano).keys())
        return self._br[ano]

    def e_dia_util(self, dia: date) -> bool:
        if dia.weekday() >= 5:  # sábado=5, domingo=6
            return False
        return dia not in self._feriados(dia.year) and dia not in self._extras

    def dia_util_anterior(self, dia: date) -> date:
        d = dia - timedelta(days=1)
        while not self.e_dia_util(d):
            d -= timedelta(days=1)
        return d

    def proximo_dia_util(self, dia: date) -> date:
        d = dia + timedelta(days=1)
        while not self.e_dia_util(d):
            d += timedelta(days=1)
        return d

    def ultimo_dia_util(self, hoje: date | None = None) -> date:
        """Último dia útil estritamente anterior a hoje (data_ref padrão)."""
        return self.dia_util_anterior(hoje or date.today())

    def rolar_para_dia_util(self, dia: date) -> date:
        """Mapeia um dia qualquer para o dia útil ao qual seus eventos pertencem
        (o próprio dia, se útil; senão o dia útil anterior)."""
        return dia if self.e_dia_util(dia) else self.dia_util_anterior(dia)

    def fim_janela(self, data_ref: date) -> date:
        """Último dia (inclusive) cujos eventos acumulam em data_ref."""
        return self.proximo_dia_util(data_ref) - timedelta(days=1)
