"""
Checks that the generator does what Annex A5 and the hypotheses say.

    python3 -m unittest test_simular -v      (from simulation/, with numpy, pandas, scipy)

Not part of the web suites: it needs the scientific stack.
"""

import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sim", HERE / "01_simular.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


def generate(n=150, seed=20261103):
    sim.N_PARTICIPANTES = n
    sim.N_MUJERES = int(round(n * 0.54))
    rng = np.random.default_rng(seed)
    participants, square = sim.generar_participantes(rng)
    episodes = sim.generar_episodios(participants, square, rng)
    rounds = sim.generar_rondas(participants, episodes, rng)
    episodes_full = sim.agregar_medidas_post(episodes, participants, rng)
    dirty_rounds, dirty_episodes = sim.ensuciar(rounds, episodes_full, participants, rng)
    return participants, episodes_full, rounds, dirty_rounds, dirty_episodes


def icc(rounds, variable):
    d = rounds.dropna(subset=[variable]).copy()
    d["res"] = d[variable] - d.groupby(
        ["agente", "feedback", "ronda", "episodio"])[variable].transform("mean")
    groups = [g.res.values for _, g in d.groupby("id")]
    n = np.mean([len(g) for g in groups])
    between = n * np.var([g.mean() for g in groups], ddof=1)
    within = np.mean([g.var(ddof=1) for g in groups])
    return (between - within) / (between + (n - 1) * within)


class Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        (cls.participants, cls.episodes, cls.rounds,
         cls.dirty_rounds, cls.dirty_episodes) = generate()


class TestDesign(Base):

    def test_domains_are_not_confounded_with_conditions(self):
        """Paper: the assignment of domains to conditions is counterbalanced."""
        cross = pd.crosstab(self.episodes.dominio,
                            [self.episodes.agente, self.episodes.feedback])
        self.assertGreater(cross.values.min(), 30)
        self.assertLess(cross.values.max(), 45)

    def test_each_participant_has_four_different_domains(self):
        per_person = self.episodes.groupby("id").dominio.nunique()
        self.assertTrue((per_person == 4).all())

    def test_mean_age_is_the_one_the_paper_reports(self):
        self.assertAlmostEqual(self.participants.edad.mean(), 25, delta=0.5)


class TestDistributions(Base):

    def test_within_subject_correlation_holds_for_every_variable(self):
        """A5.3: r = 0.50 for the repeated measures."""
        for variable in sim.VARIABLES:
            value = icc(self.rounds, variable)
            self.assertGreater(value, 0.35, variable)
            self.assertLess(value, 0.65, variable)

    def test_no_pile_of_impossible_values_at_the_floor(self):
        self.assertLess((self.rounds.hf < 1).mean(), 0.005)
        self.assertLess((self.rounds.lf_hf < 0.05).mean(), 0.005)

    def test_no_impossible_values_at_the_top(self):
        self.assertLess(self.rounds.lf_hf.max(), 40)

    def test_skewed_variables_are_skewed_and_keep_the_table_mean(self):
        """A5.3: not Gaussian except for the self-reports; A5.5: the base means."""
        low = self.rounds[self.rounds.feedback == "validacion"]
        for variable, base in (("hf", 657.0), ("lf_hf", 2.8), ("rmssd", 42.0)):
            values = low[variable]
            self.assertGreater(values.skew(), 0.2, variable)
            self.assertAlmostEqual(values.mean() / base, 1, delta=0.2, msg=variable)


class TestCoupling(Base):

    def test_self_report_and_physiology_correlate_weakly(self):
        """A5.3: around r = 0.15, signed so more stress is positive in both."""
        person = self.rounds.groupby("id")[list(sim.VARIABLES)].mean()
        physiology = {v: (-1 if c["delta"] < 0 else 1) for v, c in sim.VARIABLES.items()
                      if v not in ("panas_n", "suds")}
        values = [person[s].corr(sign * person[v])
                  for s in ("panas_n", "suds") for v, sign in physiology.items()]
        self.assertGreater(np.mean(values), 0.08)
        self.assertLess(np.mean(values), 0.25)

    def test_the_situation_rating_predicts_the_episode_self_report(self):
        """It is the paper's covariate: A6 counts on it to reduce the variance."""
        mean_suds = self.rounds.groupby(["id", "episodio"]).suds.mean().reset_index()
        joined = self.episodes.merge(mean_suds, on=["id", "episodio"])
        r = joined.pre_malestar.corr(joined.suds)
        self.assertGreater(r, 0.15)
        self.assertLess(r, 0.5)


class TestH1b(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rounds = generate(n=1500, seed=7)[2]
        cls.wide = cls.rounds.pivot_table(
            index=["id", "episodio", "agente", "feedback"],
            columns="ronda", values="scl_media").reset_index()
        cls.wide["slope"] = (cls.wide[3] - cls.wide[1]) / 2

    def _slope(self, feedback, agent):
        row = self.wide[(self.wide.feedback == feedback) & (self.wide.agente == agent)]
        return row.slope.mean()

    def test_human_rejection_habituates_less_than_ai_rejection(self):
        difference = self._slope("rechazo", "humano") - self._slope("rechazo", "ia")
        self.assertGreater(difference, 0.05)

    def test_conductance_has_no_level_effect(self):
        """H1b and Iffland: the effect is in the slope, not in the mean."""
        level = self.rounds.groupby(["agente", "feedback"]).scl_media.mean()
        self.assertLess(level.max() - level.min(), 0.15)


class TestContamination(Base):

    def test_about_six_percent_of_rounds_go_over_the_ectopic_threshold(self):
        share = (self.dirty_rounds.prop_ectopicos > sim.PROP_ECTOPICOS).mean()
        self.assertGreater(share, 0.03)
        self.assertLess(share, 0.09)

    def test_missing_values_stay_in_the_range_of_the_annex(self):
        for variable in sim.VARIABLES:
            share = self.dirty_rounds[variable].isna().mean()
            self.assertGreater(share, 0.02, variable)
            self.assertLess(share, 0.06, variable)


class TestEpisodeMeasures(Base):

    def test_has_the_measures_of_section_2_5(self):
        for column in ("naturalidad", "credibilidad", "autenticidad", "mc_entendio",
                       "mc_tenia_sentido", "mc_interes", "mc_queria_cortar"):
            self.assertIn(column, self.episodes.columns)
        self.assertNotIn("etiqueta_reportada", self.episodes.columns)

    def test_credibility_is_0_to_100_and_follows_the_label(self):
        credibility = self.episodes.credibilidad
        self.assertGreaterEqual(credibility.min(), 0)
        self.assertLessEqual(credibility.max(), 100)
        means = self.episodes.groupby("agente").credibilidad.mean()
        self.assertGreater(means["humano"], 55)
        self.assertLess(means["ia"], 35)

    def test_naturalness_does_not_differ_by_agent(self):
        """Section 2.5: credible and natural with no systematic agent difference."""
        means = self.episodes.groupby("agente").naturalidad.mean()
        self.assertLess(abs(means["humano"] - means["ia"]), 0.3)

    def test_the_label_failure_flag_follows_the_declared_criterion(self):
        e = self.dirty_episodes
        expected = (((e.agente == "humano") & (e.credibilidad < 50))
                    | ((e.agente == "ia") & (e.credibilidad > 50)))
        self.assertTrue((e.falla_etiqueta == expected).all())
        self.assertGreater(e.falla_etiqueta.sum(), 0)

    def test_some_participants_report_suspicion_as_in_kelly(self):
        """Kelly et al.: eleven of forty-one."""
        share = self.participants.sospecha.mean()
        self.assertGreater(share, 0.15)
        self.assertLess(share, 0.40)

    def test_has_the_behavioural_measures_of_withdrawal(self):
        """Section 2.5: rejection messages are shorter, the agent makes no difference."""
        lengths = self.episodes.groupby("feedback").largo_medio_agente.mean()
        self.assertLess(lengths["rechazo"], lengths["validacion"])
        by_agent = self.episodes.groupby("agente").largo_medio_agente.mean()
        self.assertLess(abs(by_agent["humano"] - by_agent["ia"]), 8)

    def test_only_the_ai_condition_has_fallback_turns(self):
        """A person has no fixed lines to fall back on."""
        turns = self.episodes.groupby("agente").turnos_respaldo.sum()
        self.assertEqual(turns["humano"], 0)
        self.assertGreater(turns["ia"], 0)

    def test_the_ai_wait_follows_the_latency_formula(self):
        ai = self.episodes[self.episodes.agente == "ia"]
        expected = 3 * (1.2 + 0.045 * ai.largo_medio_agente)
        self.assertTrue(np.allclose(ai.espera_acumulada_s, expected, atol=0.01))

    def test_the_human_wait_comes_from_reading_and_typing(self):
        """Longer than the AI's, grows with the length, and not an exact formula."""
        human = self.episodes[self.episodes.agente == "humano"]
        ai = self.episodes[self.episodes.agente == "ia"]
        self.assertGreater(human.espera_acumulada_s.min(), ai.espera_acumulada_s.max() * 0.8)
        self.assertGreater(human.espera_acumulada_s.mean(), 3 * ai.espera_acumulada_s.mean())
        r = human.espera_acumulada_s.corr(human.largo_medio_agente)
        self.assertGreater(r, 0.4)
        self.assertLess(r, 0.95)

    def test_people_vary_more_than_the_model_in_message_length(self):
        sd = self.episodes.groupby(["agente", "feedback"]).largo_medio_agente.std()
        for feedback in ("validacion", "rechazo"):
            self.assertGreater(sd[("humano", feedback)], sd[("ia", feedback)] * 1.2)

    def test_a_rating_of_nine_or_more_raises_the_alert(self):
        e = self.episodes
        self.assertTrue((e.alerta_malestar == (e.pre_malestar >= 9)).all())


if __name__ == "__main__":
    unittest.main()
