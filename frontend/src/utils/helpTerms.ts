/**
 * Help Terms Library — tooltip definitions for statistical terms.
 * 
 * Every technical term in the app should have an entry here.
 * Display these as ? icon tooltips on hover/keyboard focus.
 * 
 * Usage:
 *   import { HELP_TERMS } from '../utils/helpTerms'
 *   <Tooltip title={HELP_TERMS['independent_groups']}>independent groups ?</Tooltip>
 */

export const HELP_TERMS: Record<string, string> = {
  independent_groups:
    'Different participants in each group; no one appears in more than one group.',
  paired_data:
    'The same participants measured twice, or observations linked in matched pairs.',
  continuous:
    'A numeric variable that can take any value within a range (e.g., age, blood pressure).',
  binary:
    'A variable with exactly 2 possible values (e.g., yes/no, 0/1, alive/dead).',
  nominal:
    'Categories with no natural order (e.g., blood type, diagnosis).',
  ordinal:
    'Categories with a natural order (e.g., mild/moderate/severe, Stage I/II/III).',
  categorical_variable:
    'A variable that takes one of a limited set of values (e.g., diagnosis, treatment arm).',
  time_to_event:
    'A variable recording how long until an event occurred (e.g., survival months).',
  event_indicator:
    'A variable showing whether the event happened (1 = yes, 0 = no / censored).',
  censoring:
    'Follow-up ended before the event occurred, so the exact event time is not known.',
  mean:
    'The arithmetic average. Appropriate for symmetric continuous data.',
  median:
    'The middle value. Appropriate for skewed data or ordinal variables.',
  standard_deviation:
    'SD: A measure of spread around the mean. Appropriate for symmetric continuous data.',
  interquartile_range:
    'IQR: the range of the middle 50% of the data (Q3 − Q1).',
  confidence_interval:
    'A range that plausibly contains the true population value, usually at the 95% level.',
  correlation:
    'A measure of association between two variables, ranging from −1 to +1.',
  pearson:
    'Pearson correlation measures linear relationships. Spearman is recommended for non-linear monotonic relationships.',
  logistic_regression:
    'Used when the outcome is binary (e.g., yes/no, alive/dead).',
  cox_regression:
    'Used when the outcome is time-to-event with censoring.',
  survival:
    'Analysis of time until a specific event occurs. Accounts for censored observations.',
  normality:
    'Whether the data follows a bell-shaped (normal) distribution. Many parametric tests assume normality.',
  proportional_hazards:
    'The assumption that the effect of predictors on the hazard is constant over time.',
  fishers_exact:
    'An alternative to chi-square when expected counts in any cell are below 5.',
  kappa:
    "Cohen's kappa: a measure of agreement between two raters, adjusted for chance.",
  effect_size:
    'A standardised measure of the magnitude of an effect (e.g., Cohen\'s d, η²).',
  post_hoc:
    'Follow-up comparisons after a significant ANOVA result to identify which groups differ.',
  sensitivity:
    'The proportion of true positives correctly identified (TP / [TP + FN]).',
  specificity:
    'The proportion of true negatives correctly identified (TN / [TN + FP]).',
  auc:
    'Area Under the ROC Curve: a measure of diagnostic accuracy, ranging from 0.5 (random) to 1.0 (perfect).',
  p_value:
    'The probability of observing the data (or more extreme) if the null hypothesis is true.',
  test_statistic:
    'A single number calculated from the data that is used to determine the p-value.',
  degrees_of_freedom:
    'DF: roughly the number of independent pieces of information available to estimate a parameter.',
  hazard_ratio:
    'HR: the ratio of hazard rates between two groups. HR > 1 means higher risk in the numerator group.',
  odds_ratio:
    'OR: the ratio of odds of an event between two groups. OR > 1 means higher odds in the numerator group.',
  r_squared:
    'R²: the proportion of variance in the outcome explained by the model (0 to 1).',
  cronbach_alpha:
    "Cronbach's alpha: a measure of internal consistency reliability, ranging from 0 to 1.",
}

/**
 * Get help text for a term. Returns empty string if not found.
 */
export function getHelpText(term: string): string {
  return HELP_TERMS[term] ?? ''
}
