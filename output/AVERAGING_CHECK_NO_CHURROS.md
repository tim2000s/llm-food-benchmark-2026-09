# Median of k calls against a single call

Resampled from the calls already made: 2000 subsets of k calls per photograph, the same subsets for every arm, seed 20260921. Each cell is the median across photographs of the spread of the k-call median, in grams of carbohydrate. The width is the distance between the 5th and 95th percentiles, so nine answers in ten fall inside it. Mean absolute error is against the reference values in usda_reference.json. Excluded: MVIMG_20260222_204918.jpg.

| arm | k | SD (g) | 5-95% width (g) | mean abs. error (g) |
|---|---|---|---|---|
| fable-5-1 | 1 | 3.3 | 11.7 | 8.1 |
| fable-5-1 | 3 | 2.4 | 7.0 | 7.7 |
| fable-5-1 | 5 | 1.9 | 5.0 | 7.6 |
| gpt-5-4-april | 1 | 2.4 | 5.7 | 20.5 |
| gpt-5-4-april | 3 | 1.8 | 4.7 | 21.0 |
| gpt-5-4-april | 5 | 1.6 | 3.6 | 21.2 |
| gpt-5-4-default | 1 | 6.2 | 19.8 | 15.4 |
| gpt-5-4-default | 3 | 3.9 | 12.9 | 14.9 |
| gpt-5-4-default | 5 | 3.1 | 9.2 | 14.7 |
| gpt-6-astra | 1 | 3.4 | 10.9 | 15.2 |
| gpt-6-astra | 3 | 2.4 | 7.6 | 14.9 |
| gpt-6-astra | 5 | 1.9 | 6.2 | 14.8 |
| sonnet-4-6-april | 1 | 1.3 | 3.1 | 10.6 |
| sonnet-4-6-april | 3 | 0.8 | 2.5 | 10.5 |
| sonnet-4-6-april | 5 | 0.8 | 2.0 | 10.5 |
| sonnet-4-6-default | 1 | 3.1 | 8.4 | 10.0 |
| sonnet-4-6-default | 3 | 2.1 | 5.8 | 9.7 |
| sonnet-4-6-default | 5 | 1.6 | 5.1 | 9.6 |

## By photograph, 5-95% width (g)

| photograph | n | ref (g) | fable-5-1 k=1 | fable-5-1 k=3 | fable-5-1 k=5 | gpt-5-4-april k=1 | gpt-5-4-april k=3 | gpt-5-4-april k=5 | gpt-5-4-default k=1 | gpt-5-4-default k=3 | gpt-5-4-default k=5 | gpt-6-astra k=1 | gpt-6-astra k=3 | gpt-6-astra k=5 | sonnet-4-6-april k=1 | sonnet-4-6-april k=3 | sonnet-4-6-april k=5 | sonnet-4-6-default k=1 | sonnet-4-6-default k=3 | sonnet-4-6-default k=5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IMG-20260410-WA0016.jpg | 50 | 34 | 11.0 | 6.0 | 5.6 | 6.4 | 6.4 | 6.4 | 23.6 | 15.8 | 14.4 | 35.7 | 22.3 | 19.2 | 6.8 | 6.2 | 5.7 | 7.2 | 5.9 | 5.6 |
| IMG-20260410-WA0017.jpg | 50 | n/a | 13.8 | 8.0 | 4.8 | 2.9 | 2.9 | 2.9 | 33.2 | 25.2 | 19.7 | 11.9 | 8.9 | 7.7 | 6.8 | 5.8 | 5.8 | 21.0 | 13.9 | 12.2 |
| IMG-20260410-WA0018.jpg | 46 | n/a | 14.1 | 9.2 | 8.8 | 9.5 | 6.8 | 5.9 | 20.5 | 12.4 | 9.7 | 8.4 | 6.0 | 5.4 | 7.4 | 6.9 | 5.7 | 14.2 | 10.6 | 8.5 |
| IMG-20260410-WA0019.jpg | 50 | n/a | 2.2 | 2.2 | 2.2 | 0.0 | 0.0 | 0.0 | 5.3 | 3.0 | 2.6 | 1.8 | 0.0 | 0.0 | 1.5 | 1.5 | 1.5 | 4.5 | 4.5 | 3.1 |
| IMG-20260410-WA0020.jpg | 49 | n/a | 25.5 | 13.5 | 13.5 | 51.2 | 50.8 | 50.1 | 58.0 | 45.5 | 32.9 | 28.9 | 16.4 | 15.0 | 109.0 | 73.0 | 7.4 | 17.1 | 9.6 | 8.8 |
| IMG_20200412_154249.jpg | 50 | 47.5 | 15.3 | 8.9 | 7.0 | 17.8 | 9.9 | 8.0 | 19.1 | 13.3 | 10.6 | 6.2 | 4.8 | 4.0 | 22.5 | 18.8 | 16.0 | 27.6 | 21.1 | 16.1 |
| IMG_20250915_112359.jpg | 49 | 40 | 8.1 | 3.3 | 2.9 | 4.9 | 2.4 | 0.1 | 9.8 | 7.4 | 7.4 | 9.8 | 5.6 | 4.6 | 3.3 | 2.2 | 2.2 | 6.8 | 5.8 | 3.9 |
| IMG_20260209_192318.jpg | 50 | 60 | 17.2 | 13.8 | 12.1 | 0.0 | 0.0 | 0.0 | 15.6 | 6.1 | 4.2 | 18.1 | 14.1 | 6.1 | 2.0 | 1.7 | 1.7 | 2.8 | 2.5 | 0.8 |
| IMG_20260210_142258.jpg | 50 | 40 | 2.7 | 2.4 | 2.0 | 44.8 | 9.6 | 4.3 | 39.5 | 30.1 | 8.6 | 2.9 | 2.3 | 2.3 | 0.2 | 0.0 | 0.0 | 1.2 | 0.3 | 0.2 |
| MVIMG_20260303_200132.jpg | 50 | 58 | 12.4 | 7.6 | 5.2 | 0.0 | 0.0 | 0.0 | 16.6 | 9.7 | 4.4 | 21.1 | 16.2 | 10.9 | 3.0 | 2.8 | 0.0 | 11.4 | 5.6 | 5.6 |
| MVIMG_20260304_120022.jpg | 50 | 47.5 | 5.2 | 3.8 | 2.4 | 2.9 | 2.9 | 2.9 | 14.0 | 11.0 | 7.2 | 9.4 | 6.3 | 6.3 | 0.0 | 0.0 | 0.0 | 3.4 | 3.4 | 2.9 |
| MVIMG_20260308_142023.jpg | 48 | 40 | 8.8 | 6.4 | 4.0 | 49.1 | 13.6 | 11.2 | 52.1 | 42.1 | 37.9 | 17.4 | 12.2 | 11.5 | 1.9 | 1.5 | 1.3 | 9.6 | 5.8 | 4.5 |
