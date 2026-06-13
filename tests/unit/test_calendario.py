from datetime import date

from etl.calendario import CalendarioUtil


def test_fim_de_semana_rola_para_dia_util_anterior():
    cal = CalendarioUtil()
    sexta = date(2026, 6, 12)
    assert cal.rolar_para_dia_util(date(2026, 6, 13)) == sexta  # sábado
    assert cal.rolar_para_dia_util(date(2026, 6, 14)) == sexta  # domingo
    assert cal.rolar_para_dia_util(sexta) == sexta


def test_janela_de_extracao():
    cal = CalendarioUtil()
    assert cal.fim_janela(date(2026, 6, 12)) == date(2026, 6, 14)  # sex -> dom
    assert cal.fim_janela(date(2026, 6, 10)) == date(2026, 6, 10)  # meio de semana


def test_feriado_extra():
    cal = CalendarioUtil(feriados_extras=[date(2026, 6, 11)])
    assert not cal.e_dia_util(date(2026, 6, 11))
    assert cal.rolar_para_dia_util(date(2026, 6, 11)) == date(2026, 6, 10)
    assert cal.fim_janela(date(2026, 6, 10)) == date(2026, 6, 11)


def test_feriado_nacional():
    cal = CalendarioUtil()
    assert not cal.e_dia_util(date(2026, 9, 7))  # Independência (segunda-feira)
    assert cal.rolar_para_dia_util(date(2026, 9, 7)) == date(2026, 9, 4)
