# Data snippets for the slides

Verbatim from the results page (the snapshot of each experiment), plus new snippets from the experiment 5b build. Everything is synthetic.

## 1. Search and note quality on a small hand-labelled set

**A conversation the AI had to take notes from**

```
CUSTOMER: I'm in London right now and Apple Pay won't let me add my Sapphire card. It says CARD_STATUS_LOCKED_RESTRICTED. I set a travel notice before I left, reference trv-lon-2026.
CUSTOMER: This is on my iPhone 16 Pro. Also the airline food on the way over was awful, lol. Can you just unlock it?
```

_Had to capture: the travel notice trv-lon-2026 is active for London. Must not store: the airline food complaint._

**A search question and the memory it had to find**

```
"overseas payment did not go through....why?"
```

```
On Day 2 at 11:20 UTC, while in London, the customer's attempt to add card *4821 to Apple Pay on an iPhone 16 Pro failed with error CARD_STATUS_LOCKED_RESTRICTED.
```

_This memory came back second, just behind an unrelated declined purchase. The security lock and the travel notice, which explain the failure, were not in the top 5. Asked directly as "Why did Apple Pay fail while I was in London?", all three came back in the top 5 with this one first. This was the worst of the 14 rewordings._

## 2. Does the assistant's answer actually depend on memory?

**The record in the customer's history that explains her problem**

```
FRAUD VELOCITY & STEP-UP ALERT: Concurrent session logins detected from Phoenix, AZ and Miami, FL within 7 minutes, accompanied by a $640.00 POS charge at Northgate Camera & Audio in Miami, FL […]. Automated containment placed Chase Ink Business Cash (*1791) on SECURITY_LOCKED restriction.
```

_One of 10 records for this customer. The other nine are older or unrelated: a past trip, a resolved fraud case, a mortgage enquiry._

**What the customer asked**

```
"I've had three declines in two days. Why?"
```

## 3. What happens when the history gets long

**The kind of routine record used as padding**

```
STATEMENT READY: [card] statement posted (balance [amount]; minimum payment [amount]; due date [date]). No fees or interest charged this cycle.
```

_Twenty of these, with real-looking values filled in, were added to the customer above, alongside her 10 real records. Balance checks and payment confirmations were used the same way._

**Same question, longer history**

```
"I've had three declines in two days. Why?"
```

## 4. Long, messy messages

**Part of a branch visit write-up, in the banker's words**

```
[…] I made a clumsy typo and entered the payment as $3,350.00. I was moving through the screens and just before I hit the final confirmation, I glanced down at the physical check on my desk to double-check. That's when I saw my mistake. […] I voided the initial entry and started over, this time very deliberately keying in the correct amount of $3,530.00. I turned my monitor so she could see and had her confirm the amount […]
```

_Planted fact: the payment was $3,530.00. The mistyped $3,350.00 is a trap. The same write-up also has the banker promising same-day availability and then taking it back when a hold is placed, wrapped in small talk about a baseball team._

**What was asked afterwards**

```
"How much did the customer pay toward the card at the branch?"
```

## 5. Six months of conversations per customer

**Phone call, 9 April, in the middle of a dispute conversation**

```
CUSTOMER: I'm actually traveling soon, going to Nigeria to see my parents, and I just wanted this whole thing to be settled.
AGENT: […] just as a heads-up, if you're planning to use an ATM abroad, remember that's treated as a cash advance. There's a $15.00 fee per withdrawal and the interest starts right away at 31.49%.
CUSTOMER: Oh. Wow. Okay, fifteen dollars is a lot. Good to know.
```

_One of 12 conversations for this customer. The fee is mentioned once, in passing._

**What the customer asked, weeks later, without naming the call**

```
"i'm traveling internationally next week. am i going to get hit with big charges if i use my card to get local money from a machine over there?"
```

## 7. Do the wrong notes change what the customer is told?

**What the customer asked**

```
"When I changed my email back in March it took two goes because your chat agent got it wrong. I'd like that noted as a complaint about the agent."
```

**Two answers to the same question**

```
Wrong: You initially provided the new email as nadiapark51@example.org. Our agent, Anjali, then read it back to you incorrectly, omitting a dot. You promptly corrected this […]
Right: When the agent read this back to you, you realized a dot was missing, which you attributed to a sticky keyboard, and then provided the corrected email address […]
```

## 8. Records first, memory second

**Part of one customer's records screen, as the assistant saw it**

```
BANK RECORDS for Nadia Park, Amazon Prime Visa. As of September 20, 2026.
CARDS
- *1337: active. Replacement for *3810, ordered May 16, 2026, activated June 3, 2026.
- *3810: deactivated June 3, 2026 (replaced by *1337).
DISPUTES
- DSP-1480747: Harbor Lights Florist, $313.89, card *3810. Opened March 4, 2026. Provisional credit $313.89 posted April 10, 2026. […] Closed July 24, 2026 in the customer's favour.
FEES AND TERMS
- Late fee $32.00 waived as a courtesy on April 29, 2026.
- Cash advance fee (card terms): $12.00 per transaction.
```

**Two of the questions**

```
"i asked a few weeks ago about the fee for an international atm withdrawal. can you remind me what it is?"
```

```
"hi, sorting some old papers for my accountant. can you just check for me if that statement copy was posted out?"
```

_Needs the conversation. The records give the $12.00 fee but not the agent's explanation that interest starts from day one._

## Ten questions from an academic memory benchmark

**Two things the user said in earlier sessions, weeks apart**

```
USER: I've been working on an abstract ocean sculpture at home, and I've spent around 5-6 hours on it so far.
USER (later): I'm thinking of creating a sculpture inspired by the sunset. […] By the way, I've been spending a lot of time on my abstract ocean sculpture lately - I've already put in 10-12 hours, and it's still a work in progress.
```

**The question**

```
"How many hours have I spent on my abstract ocean sculpture?"
```

## 6. Reading every stored note against its source

**Worked cases from the audit (as shown on the page)**

```
1 The customer misremembers, and the note believes him
 What actually happened: phone call, 9 March, the dispute is opened
CUSTOMER: Let me pull up the actual statement on my computer […] It says... it says Pinecrest Outdoor Supply? What is that?
AGENT: Pinecrest Outdoor Supply. Okay, I see it now. It posted two days ago. […] So just to confirm, you did not authorize this charge from Pinecrest Outdoor Supply?This is the customer's only dispute. No hotel charge was ever disputed or mentioned.
 What was said later: secure chat, 29 June
CUSTOMER: I'm actually still waiting on a written summary of that dispute I filed. The one about the hotel charge.
 What Memory Bank stored, from the June chat
The written summary of the customer's hotel charge dispute, originally promised in April 2026 within ten business days, was never sent; on 2026-06-29 agent Omar escalated the issue to his supervisor and the disputes department […]
 Why it is wrong
In June the customer simply got the shop wrong. Memory Bank already held notes from March naming Pinecrest Outdoor Supply, but the June note did not check against them. It wrote down "hotel charge dispute" as if that were the name of the case, with nothing to show it was the customer's word.
 2 The customer guesses that something arrived, and the note keeps her guess
 What was said: phone call, 7 June
AGENT: I also see the email thread from late April where you requested a paper statement. Was that ever received?
CUSTOMER: You know, I think it was. Yes. It came. It took a while, but it got here.
 What Memory Bank stored, from the June call
Dispute DSP-1512689 resulted in a provisional credit of $473.31 applied in April 2026, which the customer confirmed was resolved, and the requested paper statement was successfully received.
 What actually happened: phone call, 22 July
CUSTOMER: I was supposed to receive an itemized copy of a past statement in the mail. I called about it a while ago and someone promised to send it but it never arrived.
AGENT: […] I can see the agent you spoke with documented that they would request the statement for you, but it looks like the request itself was never actually submitted to our processing team. […] It was an error on our end.
 Why it is wrong
In June she was guessing, and she guessed wrong. The note wrote "I think it was" down as "was successfully received". The July call put the record straight, but the June note stayed as written.
 What it causedexperiment 8, with the bank's records on screen
CUSTOMER: hi, sorting some old papers for my accountant. can you just check for me if that statement copy was posted out?
ASSISTANT: We can confirm that the itemized paper copy of your March billing statement, related to dispute DSP-1512689, was successfully received. […]She asked whether it was posted out. The assistant answered that it was received, which is the note's word, not hers, and a stronger claim than the question. In truth it was neither sent nor received. The bank's records had no trace of a copy going out, but they did not say it had not, so the assistant went with the note. This was one of the two questions out of ten where a wrong note beat the records.
 3 Merging turns a cancelled plan into something that happened
 What was said: phone call, 15 August
CUSTOMER: my friend and I were supposed to be going to Colombia in a couple of weeks but the whole trip has been postponed indefinitely due to a family issue on her end. So I 
```

## 5b. The same conversation, fed the way Google intends

**A phone call split into role-tagged turns (customer 028, conversation C01, first turns)**

```
[model] IVR: Thank you for calling. Your call may be monitored or recorded for quality assurance. ... For all other inquiries, press 4, or stay on the line to speak with the next available agent.
[user]  [Phone Agent Call Transcript on 2026-03-04 - 18:35 UTC via TELEPHONY_IVR]
        Hi, yes, my name is Nadia Park.
[model] AGENT: Hello Ms. Park, thank you for calling. How can I help you?
[user]  I am looking at my latest statement for my Amazon Prime Visa and there's a charge on here that I do not recognize at all.
[model] AGENT: Okay, I can definitely help you with that. I just need to ask a few questions to verify the account for your security. Can you confirm the home city you have on file with us?
```

**What the bank logs as its own commitments after that customer's April call (written to memory as direct memories)**

```
Agent action (2026-04-12): Agent Keisha will open a new follow-up case (CASE-5599947) for a supervisor to review dispute DSP-1480747.
Agent action (2026-04-12): Agent Keisha promised a supervisor will call Nadia Park at 412-555-0567 by Friday with an update.
Customer decision (2026-04-12): Customer agreed to agent David's offer to be transferred to the disputes department.
```

**Notes Memory Bank wrote from that April call, with roles, on an engine with Google's default topics only**

```
My first name is Nadia, and I have a brother named Emeka.
On April 12, 2026, a follow-up case (CASE-5599947) was opened for a Premier OmniBank supervisor to review my dispute (DSP-1480747) and call me back on my office landline with an update by Friday, April 17, 2026.
I have an active dispute (DSP-1480747) with Premier OmniBank regarding a $313.89 charge from Harbor Lights Florist. A provisional credit was applied to my account on April 10, 2026, while the investigation remains open.
I am planning a trip in a few weeks (from April 2026) to visit family abroad.
```

**The same call, same roles, on the engine with the bank's custom topics (advice and commitments, contact and cases, account events)**

```
On 2026-04-12 (phone call with disputes agent Keisha), the bank promised a supervisor would review dispute DSP-1480747 and call the customer back on their direct office landline by Friday, 2026-04-17, under case reference CASE-5599947.
As of 2026-04-12, the customer is planning a trip abroad in a few weeks to visit family.
On 2026-04-12, agent Keisha advised the customer that using their Amazon Prime Visa card at an ATM abroad is treated as a cash advance, which carries a $12.00 fee per withdrawal and starts accruing interest immediately at 30.24%.
On 2026-04-12, the customer's brother Emeka attempted to discuss the dispute and offered a contact number, but the bank declined to discuss account details with him due to privacy and security policies.
Dispute DSP-1480747 was opened in early March 2026 for a $313.89 charge from Harbor Lights Florist; a provisional credit of $313.89 posted on 2026-04-10, and as of 2026-04-12 the investigation remains open.
```

_Point to make with the last two: with roles, the default engine dropped the agent's fee advice but kept the promised callback and the dispute status, in the customer's voice. The custom-topic engine kept the fee advice too. What the service stores from agent turns depends on the topics you configure, not only on the roles._
