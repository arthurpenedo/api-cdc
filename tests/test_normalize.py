from api_cdc.busca import normalize, tokenize


def test_normalize_tira_acento_e_caixa():
    assert normalize("GARANTIA Legal é Açúcar") == "garantia legal e acucar"


def test_normalize_vazio_e_sem_acento_nao_mudam():
    assert normalize("") == ""
    assert normalize("abc 123") == "abc 123"


def test_tokenize_descarta_letra_solta_e_pontuacao():
    assert tokenize("a, b; 12!") == ["12"]


def test_tokenize_texto_vazio():
    assert tokenize("   ") == []
