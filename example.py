import eyepystan
import pystan

#model from pystan example https://github.com/stan-dev/pystan/
schools_code = """
data {
    int<lower=0> J; // number of schools
    real y[J]; // estimated treatment effects
    real<lower=0> sigma[J]; // s.e. of effect estimates
}
parameters {
    real mu;
    real<lower=0> tau;
    real eta[J];
}
transformed parameters {
    real theta[J];
    for (j in 1:J)
        theta[j] = mu + tau * eta[j];
}
model {
    eta ~ normal(0, 1);
    y ~ normal(theta, sigma);
}
"""

schools_dat = {'J': 8,
               'y': [28,  8, -3,  7, -1,  1, 18, 12],
               'sigma': [15, 10, 16, 11,  9, 11, 10, 18]}

filename = "/tmp/reloadstanfit"
import pickle
try:
  f = open(filename, "rb")
  sm, fit = pickle.load(f)
except IOError:
  sm = pystan.StanModel(model_code=schools_code)
  fit = sm.sampling(data=schools_dat, iter=1000, chains=4)
  f = open(filename, "wb")
  pickle.dump([sm, fit], f)
finally:
  f.close()

app = eyepystan.App(fit, sm)
app.run()
