import json

from app.services.llm.skill_bootstrap import BOOTSTRAP_META_KEY, bootstrap_agent_skills_into_settings, extract_agent_skills_from_payload


def test_extract_agent_skills_from_proposal_payload() -> None:
    payload = {
        'skills': [
            {
                'id': 'repo-a:risk-management',
                'skill_name': 'risk-management',
                'description': 'Valider le risque avant chaque entree.',
                'evidence': {
                    'notable_points': [
                        'Toujours exiger un stop-loss.',
                        'Adapter la frequence au regime.',
                    ],
                },
            },
            {
                'id': 'repo-b:macro-view',
                'skill_name': 'macro-view',
                'description': 'Qualifier le regime risk-on/risk-off.',
            },
        ],
        'agent_mapping': {
            'news-analyst': {
                'primary_skills': ['repo-a:risk-management'],
                'secondary_skills': ['repo-b:macro-view'],
                'notes': 'Eviter les recits non verifies.',
            },
            'risk-manager': {
                'primary_skills': ['repo-a:risk-management'],
            },
        },
    }

    result = extract_agent_skills_from_payload(payload)

    assert 'news-analyst' in result
    assert any('risk-management' in line for line in result['news-analyst'])
    assert any('macro-view' in line for line in result['news-analyst'])
    assert any('Contexte agent:' in line for line in result['news-analyst'])
    assert 'risk-manager' in result


def test_bootstrap_agent_skills_merge_and_apply_once(tmp_path) -> None:
    payload = {
        'agent_skills': {
            'news-analyst': ['Prioriser events macro', 'Citer les risques'],
            'trader-agent': 'Favoriser HOLD si conflit',
        }
    }
    bootstrap_file = tmp_path / 'skills.json'
    bootstrap_file.write_text(json.dumps(payload), encoding='utf-8')

    current_settings = {
        'provider': 'ollama',
        'agent_skills': {
            'news-analyst': ['Sources fiables uniquement'],
        },
    }

    updated_settings, changed, status = bootstrap_agent_skills_into_settings(
        current_settings=current_settings,
        bootstrap_file=str(bootstrap_file),
        mode='merge',
        apply_once=True,
    )

    assert changed is True
    assert status == 'applied'
    assert updated_settings['agent_skills']['news-analyst'] == [
        'Sources fiables uniquement',
        'Prioriser events macro',
        'Citer les risques',
    ]
    assert updated_settings['agent_skills']['trader-agent'] == ['Favoriser HOLD si conflit']
    assert BOOTSTRAP_META_KEY in updated_settings

    updated_settings_2, changed_2, status_2 = bootstrap_agent_skills_into_settings(
        current_settings=updated_settings,
        bootstrap_file=str(bootstrap_file),
        mode='merge',
        apply_once=True,
    )

    assert changed_2 is False
    assert status_2 == 'already-applied'
    assert updated_settings_2 == updated_settings


def test_bootstrap_agent_skills_replace_mode_replaces_existing_entries(tmp_path) -> None:
    payload = {
        'agent_skills': {
            'news-analyst': ['Nouveau skill unique'],
        }
    }
    bootstrap_file = tmp_path / 'skills-replace.json'
    bootstrap_file.write_text(json.dumps(payload), encoding='utf-8')

    current_settings = {
        'agent_skills': {
            'news-analyst': ['Ancien skill'],
            'trader-agent': ['Skill trader existant'],
        },
    }

    updated_settings, changed, status = bootstrap_agent_skills_into_settings(
        current_settings=current_settings,
        bootstrap_file=str(bootstrap_file),
        mode='replace',
        apply_once=False,
    )

    assert changed is True
    assert status == 'applied'
    assert updated_settings['agent_skills'] == {'news-analyst': ['Nouveau skill unique']}
