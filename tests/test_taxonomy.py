import pytest

from mta.taxonomy import default_taxonomy, normalise


@pytest.mark.parametrize("raw, expected", [
    ("  META | Prospecting | Lookalike 1% ", "meta_prospecting_lookalike_1%"),
    ("GS-Brand-Exact", "gs_brand_exact"),
    ("PMax__Bestsellers ", "pmax_bestsellers"),
    ("", ""),
    (None, ""),
    (float("nan"), ""),
])
def test_normalise(raw, expected):
    assert normalise(raw) == expected


@pytest.mark.parametrize("source, medium, campaign, channel", [
    ("google", "cpc", "GS_Brand_Exact", "Google Search Brand"),
    ("Google", "CPC", "gs-brand-phrase ", "Google Search Brand"),
    ("google", "paid", "GS_Generic_Cold_Brew", "Google Search Generic"),
    ("google", "cpc", "PMax_Bestsellers", "Google PMax"),
    ("facebook", "paid_social", "META_Retargeting_ATC_7d", "Meta Retargeting"),
    ("Facebook", "paid_social", "META | Prospecting | Lookalike 1%", "Meta Prospecting"),
    ("apple", "cpc", "ASA_Brand", "Apple Search Ads"),
    ("partner", "affiliate", "AFF_Partner_Coupons", "Affiliate"),
    ("newsletter", "email", "EM_Winback_30d", "Email"),
    ("google", "organic", "", "Organic Search"),
    ("blog.example.com", "referral", "", "Referral"),
    ("(direct)", "(none)", "", "Direct"),
    ("google", "cpc", "test_campaign_do_not_use", "Unmapped"),
    ("facebook", "paid_social", "test_campaign_do_not_use", "Unmapped"),
])
def test_resolve(source, medium, campaign, channel):
    assert default_taxonomy().resolve(source, medium, campaign)[0] == channel


def test_paid_flag():
    tax = default_taxonomy()
    assert tax.resolve("google", "cpc", "GS_Brand_Exact")[1] is True
    assert tax.resolve("google", "organic", "")[1] is False


@pytest.mark.parametrize("platform, campaign, channel", [
    ("Google Ads", "GS_Competitor_Terms", "Google Search Generic"),
    ("Meta Ads", "META | Prospecting | Lookalike 1%", "Meta Prospecting"),
    ("Apple Search Ads", "ASA_Generic", "Apple Search Ads"),
    ("Affiliate Network", "AFF_Partner_Content", "Affiliate"),
])
def test_resolve_spend(platform, campaign, channel):
    assert default_taxonomy().resolve_spend(platform, campaign)[0] == channel
