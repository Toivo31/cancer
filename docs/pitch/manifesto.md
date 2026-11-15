# Automation arrives

Nov 15, 2026 · Tuomas Talasmaa

Every step in healthcare consists of two things: an execution and a decision. A nurse takes a sample, and someone decides what it means. A doctor sees a patient, and someone decides what happens next. Together, care pathways form a node graph, where patients travel from node to node until they are diagnosed and treated.

More and more of these nodes will be automated. We have already seen the first symptom assessment automated through self-reporting questionnaires and assessments. Next come chatbots and humanoids taking on parts of nursing work, and robotic arms or automated machines collecting samples. But these inventions do not make decisions by themselves. Every automated step must be paired with a decision architecture that answers one question: given this set of facts, which test or treatment comes next? There's a limited benefit to a robotic sample collection arm if a nurse still has to decide what to do with the results.

With JEV decision models, we can build that decision architecture for healthcare. It is ready for automation one part at a time, and it leaves humans to handle the edge cases.

Meanwhile, the JEV decision architecture unlocks two concrete benefits today: better decisions and fewer errors.

JEV takes in a set of facts and gives a probability for each answer option. We calibrate the model with existing patient records: what was known at each point, and what was done next. Once calibrated, it gives the doctor a second opinion on what to do next. That might be asking for more information, ordering a specific test, referring to another expert, waiting to see, or prescribing a medication. This reduces errors and puts new treatment options within the doctor's reach.

Second, we can optimise the decisions themselves. Doctors rely on heuristics, and even when they want to, they have no way to optimise their decisions for the whole network. They decide with local, node-level information and optimise at the local level. But what if, in certain cases, we should be making systematically different decisions? If test A is usually ordered before test B for a given set of symptoms, would it be more efficient to order B first?

Our simulation framework finds these improvements. From real or synthetic data we generate patient cards with hidden variables. Some of those variables are revealed as the patient travels through the network, talking to different professionals, taking tests and trying treatments. The graph optimiser sees which nodes each patient visited and what each visit revealed. Aggregated across all patient paths, it reorders the graph by changing the decision criteria or the order and connections of the nodes. For example, it can create a rarely used but effective fast track for specific patients, which can speed up cancer detection a lot. Then we hide all the variables again, send the same patients through the altered network, and measure how long it took to diagnose and treat them and what was revealed along the way.

Every node also has a real-world cost: a limited daily capacity. The framework shows where queues build up in the current system. It simulates how targeted capacity increases or different routing would change those queues. This tells us which capacity upgrades are worth making, and which can be avoided altogether by routing patients differently.

This is automated decision-making infrastructure for healthcare, with humans in control of how decisions are made and when they are made automatically. Interpreting a blood sample in straightforward cases should already be automated; a doctor is brought in only when the results are not straightforward to interpret.

It also makes healthcare more equal. Through JEV, doctors see how their colleagues decided in similar or identical cases, and decision heuristics become standard across the system. And finally, it improves patient flow.

The framework applies to the whole of healthcare, but cancer diagnosis is where it matters most. Cancers are rare and varied, so doctors are unlikely to suspect them even when the signs are there, and they attribute the signs to more common causes. JEV can work as preventive screening: it reads patient records and gives each patient a probability of cancer based on their current symptoms and past history. A patient who comes in with a cough is usually told to rest. But if our system flags one of those cough patients with a 3% chance of lung cancer, against near zero for a typical cough patient, the doctor pays closer attention. That is the moment to order an examination and catch an early-stage lung cancer.

Finland's lung cancer outcomes trail the other Nordic countries, and Finnish patients wait longer at every step of the diagnostic pathway. Queues form in each process of a multilayered path. A patient is often first bounced between nurse appointments a few times, then sees several doctors and takes a test, and only then is referred to specialist care for a cancer diagnosis. If we cut these steps, we cut the time to diagnosis, and more cancers are found while they can still be treated with curative intent.

## Actionable insights to do now

- Use machine-assisted preventive cancer screening on patient records.
- Streamline treatment pathways and introduce fast-track lines for patients with elevated cancer risk.
- Embrace automation to streamline healthcare and reduce lead times.
