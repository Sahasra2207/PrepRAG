import json, random, re, sqlite3, uuid
from datetime import datetime, timezone
from .config import DATA_DIR
from .vector_store import get_all_chunks
DB = DATA_DIR / 'progress.db'
TOPICS = {
 'RAG & AI':['rag','retrieval','embedding','vector','llm','prompt','hallucination','generation'],
 'Programming':['python','java','javascript','function','class','loop','algorithm','complexity'],
 'DBMS & SQL':['database','sql','query','table','index','transaction','normalization','mongodb','mysql'],
 'Operating Systems':['process','thread','memory','scheduling','deadlock','cpu'],
 'Computer Networks':['network','tcp','ip','http','dns','router','protocol','packet'],
 'Web Development':['react','html','css','api','fastapi','express','node','frontend','backend'],
 'Machine Learning':['classification','regression','training','dataset','feature','prediction','knn','random forest','accuracy']}
MOCK = {
 'General':[
 ('Tell me about yourself.','Cover your degree, strongest skills, one relevant project, and target role.','HR'),
 ('Explain one project end to end.','Cover the problem, architecture, data flow, your verified contribution, one challenge, and a limitation.','Projects'),
 ('Describe a bug you investigated.','Explain the symptom, reproduction steps, evidence checked, root cause, fix, and how you verified it.','Problem solving'),
 ('What happens when you enter a URL in a browser?','Mention DNS, connection setup, TLS for HTTPS, HTTP request/response, and rendering.','Computer Networks'),
 ('Explain process vs thread.','A process has its own address space; threads in a process share memory and resources but have their own execution state.','Operating Systems'),
 ('What is normalization in DBMS?','It structures relational tables to reduce redundancy and update anomalies using normal forms.','DBMS'),
 ('Explain the four pillars of OOP.','Describe encapsulation, abstraction, inheritance, and polymorphism with an example.','OOP'),
 ('How do you analyse time complexity?','Explain how operation count grows with input size and identify the dominant term using Big-O.','DSA')],
 'Google':[
 ('Find the first non-repeating character in a string.','Use a frequency map, then scan in original order. Expected O(n) time and O(k) space.','DSA'),
 ('How would you design a URL shortener?','Discuss endpoints, unique IDs, persistent mappings, redirects, collision handling, and caching.','System design'),
 ('Hash map vs balanced tree?','Hash maps offer average O(1) lookup without ordering; balanced trees support ordered operations in O(log n).','DSA')],
 'Amazon':[
 ('Tell me about a time you took ownership.','Use a real STAR example: situation, task, action, result. Do not invent metrics.','Leadership'),
 ('Find two numbers that sum to a target.','Scan once using a hash set/map to check target minus current value; expected O(n) time.','DSA'),
 ('How would you handle a failed service dependency?','Discuss timeouts, bounded retries with backoff, graceful degradation, monitoring, and idempotency.','System design')],
 'Microsoft':[
 ('Interface vs abstract class?','An interface defines a contract; an abstract class can combine abstract methods with shared state or implementation.','OOP'),
 ('How would you debug an API returning HTTP 500?','Reproduce, inspect logs, validate inputs and dependencies, isolate the failing layer, fix root cause, and add a regression test.','Backend'),
 ('Authentication vs authorization?','Authentication verifies identity; authorization determines permitted actions.','Security')],
 'TCS':[
 ('DELETE vs TRUNCATE vs DROP?','DELETE removes selected rows, TRUNCATE removes all rows with database-specific behavior, and DROP removes the table object.','SQL'),
 ('Array vs linked list?','Arrays support O(1) indexed access; linked lists provide sequential access and can insert efficiently when the node is known.','DSA'),
 ('Why should we hire you as a fresher?','Connect your fundamentals, evidence from projects or practice, learning approach, and willingness to contribute honestly.','HR')],
 'Infosys':[
 ('Primary key vs foreign key?','A primary key uniquely identifies a row; a foreign key references a key to enforce referential integrity.','DBMS'),
 ('Explain polymorphism.','The same interface or method call can behave differently for different types, such as overridden subclass methods.','OOP')],
 'Accenture':[
 ('How do you handle unclear requirements?','Clarify goals and constraints, document assumptions, agree acceptance criteria, and iterate with stakeholders.','Situational'),
 ('GET vs POST?','GET generally retrieves resources and should be safe; POST submits data for processing or creation.','Web')]
}
def connect():
 DATA_DIR.mkdir(parents=True, exist_ok=True); c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS quizzes(id TEXT PRIMARY KEY, created TEXT, data TEXT, submitted INTEGER DEFAULT 0, score INTEGER, total INTEGER)')
 c.execute('CREATE TABLE IF NOT EXISTS quiz_answers(id INTEGER PRIMARY KEY, quiz_id TEXT, topic TEXT, correct INTEGER, created TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS mock_attempts(id INTEGER PRIMARY KEY, company TEXT, category TEXT, question TEXT, rating INTEGER, notes TEXT, created TEXT)'); c.commit(); return c
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def topic_for(s):
 low=s.lower(); scores=[(sum(w in low for w in words),name) for name,words in TOPICS.items()]; score,name=max(scores,default=(0,'General')); return name if score else 'General'
def sentences(s): return [re.sub(r'\s+',' ',x).strip(' -•') for x in re.split(r'(?<=[.!?])\s+|\n+',s) if 45 <= len(x.strip()) <= 300]
def _concept_question(item):
 """Create a learning-oriented question from a source sentence, not a quote-recognition question."""
 text=item['text']; low=text.lower(); topic=item['topic']
 # Topic-specific conceptual question banks. The source sentence is retained as evidence/explanation.
 banks = [
  (r'primary key', 'DBMS & SQL', 'Why must a primary key uniquely identify each row and disallow NULL values?',
   ['Because it identifies a specific row unambiguously.', 'Because it stores multiple values in one field.', 'Because it automatically encrypts the table.', 'Because it removes every foreign key.'], 0,
   'A primary key identifies each row uniquely, so duplicate or missing key values would make that identification unreliable.'),
  (r'foreign key|referential integrity', 'DBMS & SQL', 'What is the main purpose of a foreign key in a relational database?',
   ['To link related tables and help enforce referential integrity.', 'To guarantee that every value in the table is unique.', 'To sort all rows automatically.', 'To compress the database files.'], 0,
   'A foreign key references a key in another table and helps maintain valid relationships between records.'),
  (r'inner join', 'DBMS & SQL', 'When should you use an INNER JOIN?',
   ['When you only want rows with matching values in both tables.', 'When you need every row from the left table, even without a match.', 'When you want to delete a table.', 'When you want to remove duplicate columns from storage.'], 0,
   'An INNER JOIN returns rows where the join condition matches in both tables.'),
  (r'left join', 'DBMS & SQL', 'You need every employee in the result, including employees without a matching department. Which join fits this requirement when Employees is the left table?',
   ['LEFT JOIN', 'INNER JOIN', 'CROSS JOIN only', 'A DELETE statement'], 0,
   'A LEFT JOIN keeps every row from the left table and fills right-table columns with NULL when there is no match.'),
  (r'normalization|redundancy|anomalies', 'DBMS & SQL', 'Why is database normalization used?',
   ['To reduce unnecessary duplication and prevent insertion, update, and deletion anomalies.', 'To make every query return all rows.', 'To replace SQL with Python.', 'To guarantee that a database never needs indexes.'], 0,
   'Normalization organizes tables to reduce data redundancy and common modification anomalies.'),
  (r'atomicity', 'DBMS & SQL', 'A transaction fails halfway through a bank transfer. Which ACID property requires the operation to happen completely or not at all?',
   ['Atomicity', 'Isolation', 'Durability', 'Consistency'], 0,
   'Atomicity treats a transaction as an all-or-nothing unit.'),
  (r'consistency', 'DBMS & SQL', 'Which ACID property ensures a transaction moves the database between valid states?',
   ['Consistency', 'Atomicity', 'Isolation', 'Durability'], 0,
   'Consistency requires transactions to preserve defined database rules and constraints.'),
  (r'isolation', 'DBMS & SQL', 'Which ACID property addresses interference between concurrent transactions?',
   ['Isolation', 'Durability', 'Atomicity', 'Normalization'], 0,
   'Isolation controls how concurrent transactions interact, according to the configured isolation level.'),
  (r'durability', 'DBMS & SQL', 'After a transaction is committed, which ACID property means its changes should persist through a failure?',
   ['Durability', 'Isolation', 'Atomicity', 'Consistency'], 0,
   'Durability means committed changes persist, subject to the database system guarantees.'),
  (r'chunk overlap', 'RAG & AI', 'Why do RAG pipelines often use overlap between adjacent text chunks?',
   ['To reduce the chance that useful context is split across chunk boundaries.', 'To train the language model from scratch.', 'To encrypt the vector database.', 'To guarantee every answer is correct.'], 0,
   'Overlap repeats a small amount of text between chunks to preserve context across boundaries.'),
  (r'top-k|nearest matching chunks', 'RAG & AI', 'In retrieval-augmented generation, what does Top-K retrieval control?',
   ['How many of the nearest matching chunks are returned for the query.', 'How many model parameters are retrained.', 'The maximum size of the uploaded file in megabytes.', 'The number of users allowed to sign in.'], 0,
   'Top-K sets the number of retrieved chunks supplied as candidate context.'),
  (r'embedding|numerical representation of text', 'RAG & AI', 'What is the role of an embedding in a RAG application?',
   ['Represent text as a numerical vector so semantically related content can be searched.', 'Generate a final answer without retrieving any context.', 'Store the original PDF as an image only.', 'Guarantee the language model cannot hallucinate.'], 0,
   'Embeddings represent text numerically, enabling vector similarity search for relevant content.'),
  (r'hallucination', 'RAG & AI', 'What is a hallucination in a generative AI answer?',
   ['A claim that is incorrect or not supported by the available evidence.', 'A vector with many dimensions.', 'A successful database transaction.', 'A method for splitting documents into chunks.'], 0,
   'Grounding answers in retrieved evidence and checking citations can reduce, but not eliminate, hallucinations.'),
  (r'cosine similarity|similarity', 'RAG & AI', 'When using cosine similarity to compare embeddings, what does a higher similarity generally indicate?',
   ['The vectors point in more similar directions.', 'The documents must be identical word for word.', 'The model has been fine-tuned.', 'The database contains no metadata.'], 0,
   'Cosine similarity compares vector direction; its interpretation depends on the embedding and retrieval setup.'),
  (r'process vs thread|threads? in a process|address space', 'Operating Systems', 'What is a key difference between a process and a thread?',
   ['Processes generally have separate address spaces, while threads in a process share memory.', 'Threads always run on separate computers.', 'A process cannot contain threads.', 'Threads always use more memory than processes.'], 0,
   'Threads in the same process share process resources but have their own execution state.'),
  (r'dns', 'Computer Networks', 'What does DNS primarily do when a user accesses a website by its domain name?',
   ['Resolves a domain name to associated network records, commonly an IP address.', 'Encrypts every HTTP response automatically.', 'Renders the webpage layout.', 'Stores relational database transactions.'], 0,
   'DNS lets clients discover records associated with a domain name.'),
  (r'http request|http response|https', 'Computer Networks', 'In a typical web request, what is HTTP responsible for?',
   ['Defining the request/response communication between a client and server.', 'Assigning a primary key to every database row.', 'Converting source code directly into machine code.', 'Creating text embeddings.'], 0,
   'HTTP defines the semantics and format of client-server requests and responses; HTTPS protects HTTP using TLS.'),
  (r'classification', 'Machine Learning', 'What is the typical goal of a classification model?',
   ['Predict a category or class label for an input.', 'Predict only a continuous numeric value.', 'Store document chunks in a vector database.', 'Normalize a relational schema.'], 0,
   'Classification predicts discrete labels, while regression typically predicts continuous values.'),
  (r'regression', 'Machine Learning', 'Which task is most naturally framed as regression?',
   ['Predicting a continuous value such as tomorrow’s temperature.', 'Choosing whether an email is spam or not spam.', 'Identifying a foreign key.', 'Retrieving the nearest text chunks.'], 0,
   'Regression models are commonly used to predict continuous numerical targets.'),
 ]
 for pattern, expected_topic, question, options, correct, explanation in banks:
  if re.search(pattern, low):
   return {'question': question, 'options': options, 'correct_index': correct,
           'explanation': explanation + ' Source context: ' + text,
           'topic': expected_topic, 'document': item['document'], 'chunk': item['chunk']}
 # Generic but still conceptual prompt, grounded in the source's topic rather than quote recognition.
 words=re.findall(r"[A-Za-z][A-Za-z0-9'-]*", text)
 if len(words) >= 8:
  keyphrase=' '.join(words[:6])
  return {'question': f"Which idea is best supported by the study material about {topic}?",
          'options':[f"The material explains: {text}",
                     'The material says this topic is unrelated to the system being discussed.',
                     'The material states that this topic always guarantees perfect results.',
                     'The material recommends removing this concept entirely.'],
          'correct_index':0,
          'explanation':'This option paraphrases the source context rather than testing memorization of the exact filename. Source context: '+text,
          'topic':topic,'document':item['document'],'chunk':item['chunk']}
 return None

def generate_quiz(count=5):
 candidates=[]
 for ch in get_all_chunks():
  for sentence in sentences(ch['text']):
   candidates.append({'text':sentence,'document':ch['filename'],'chunk':ch['chunk_index'],'topic':topic_for(sentence)})
 unique={x['text'].lower():x for x in candidates}; candidates=list(unique.values())
 if not candidates: raise ValueError('Upload readable study material before generating a quiz.')
 question_pool=[]
 seen_questions=set()
 for item in candidates:
  q=_concept_question(item)
  if q and q['question'] not in seen_questions:
   question_pool.append(q); seen_questions.add(q['question'])
 if not question_pool:
  raise ValueError('The uploaded material did not contain enough recognizable concepts to build a useful quiz. Try notes with clear definitions and explanations.')
 random.shuffle(question_pool)
 selected=question_pool[:min(max(1,count),10,len(question_pool))]
 qs=[]
 for q in selected:
  # Rotate answer position to avoid making the correct answer always option A.
  correct_text=q['options'][q['correct_index']]
  options=list(q['options']); random.shuffle(options)
  q['correct_index']=options.index(correct_text); q['options']=options
  qs.append(q)
 qid=str(uuid.uuid4())
 with connect() as c: c.execute('INSERT INTO quizzes(id,created,data) VALUES(?,?,?)',(qid,now(),json.dumps(qs)))
 return {'quiz_id':qid,'total':len(qs),'questions':[{k:v for k,v in q.items() if k!='correct_index'} for q in qs], 'generation_mode':'conceptual_template_from_uploaded_material'}

def submit_quiz(qid,answers):
 with connect() as c:
  row=c.execute('SELECT * FROM quizzes WHERE id=?',(qid,)).fetchone()
  if not row: raise ValueError('Quiz not found. Generate a new quiz and try again.')
  if row['submitted']: raise ValueError('This quiz has already been submitted.')
  qs=json.loads(row['data'])
  if len(answers)!=len(qs): raise ValueError('Please answer every question before submitting.')
  review=[]; score=0; stamp=now()
  for q,a in zip(qs,answers):
   if not isinstance(a,int) or a<0 or a>=len(q['options']): raise ValueError('Invalid answer selection.')
   ok=int(a==q['correct_index']); score+=ok; c.execute('INSERT INTO quiz_answers(quiz_id,topic,correct,created) VALUES(?,?,?,?)',(qid,q['topic'],ok,stamp))
   review.append({'question':q['question'],'options':q['options'],'selected_index':a,'correct_index':q['correct_index'],'is_correct':bool(ok),'explanation':q['explanation'],'topic':q['topic'],'document':q['document'],'chunk':q['chunk']})
  c.execute('UPDATE quizzes SET submitted=1,score=?,total=? WHERE id=?',(score,len(qs),qid)); c.commit()
 return {'score':score,'total':len(qs),'percentage':round(score/len(qs)*100),'review':review}
def progress():
 with connect() as c:
  quizzes=c.execute('SELECT score,total,created FROM quizzes WHERE submitted=1 ORDER BY created DESC').fetchall(); topics=c.execute('SELECT topic,COUNT(*) n,SUM(correct) correct FROM quiz_answers GROUP BY topic').fetchall(); mocks=c.execute('SELECT company,category,question,rating,created FROM mock_attempts ORDER BY id DESC LIMIT 8').fetchall()
  total=sum(r['total'] or 0 for r in quizzes); correct=sum(r['score'] or 0 for r in quizzes); stats=[{'topic':r['topic'],'attempts':r['n'],'correct':r['correct'],'accuracy':round((r['correct'] or 0)/max(1,r['n'])*100)} for r in topics]
  weak=sorted([x for x in stats if x['attempts']>=2 and x['accuracy']<70],key=lambda x:x['accuracy'])
  return {'quiz_attempts':len(quizzes),'questions_answered':total,'overall_accuracy':round(correct/max(1,total)*100) if total else 0,'mock_practice_attempts':c.execute('SELECT COUNT(*) FROM mock_attempts').fetchone()[0],'topic_stats':stats,'weak_topics':weak,'recent_quizzes':[dict(r) for r in quizzes[:5]],'recent_mock_practice':[dict(r) for r in mocks],'note':'A topic is flagged after at least two answers with accuracy below 70%.'}
def mock_questions(company='General',category='All',count=5):
 company=company if company in MOCK else 'General'; bank=list(MOCK[company])+(MOCK['General'] if company!='General' else [])
 if category!='All':
  filtered=[q for q in bank if category.lower() in q[2].lower()]
  if filtered: bank=filtered
 seen=set(); bank=[q for q in bank if not(q[0] in seen or seen.add(q[0]))]; random.shuffle(bank)
 return {'company':company,'questions':[{'question':q[0],'answer_guide':q[1],'category':q[2]} for q in bank[:max(1,min(count,10))]],'note':'Curated practice prompts, not official or guaranteed company interview questions.'}
def save_mock(company,category,question,rating,notes=''):
 if not 1<=rating<=5: raise ValueError('Self-rating must be between 1 and 5.')
 with connect() as c: c.execute('INSERT INTO mock_attempts(company,category,question,rating,notes,created) VALUES(?,?,?,?,?,?)',(company[:80],category[:80],question[:1000],rating,notes[:2000],now())); c.commit()
 return {'saved':True,'message':'Practice attempt saved.'}
