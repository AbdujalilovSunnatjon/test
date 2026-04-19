import re
import random

def load_questions(filepath):
    """
    Loads questions from the tests.txt file and returns a list of dictionaries.
    Each dictionary has:
    - question: str
    - options: list of str
    - correct_index: int (0-indexed)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'\+{5,}', content)
    questions = []
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        parts = re.split(r'={5,}', block)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) < 3:
            continue
            
        question_text = parts[0]
        raw_options = parts[1:]
        
        correct_index = -1
        options = []
        for i, opt in enumerate(raw_options):
            if opt.startswith('#'):
                correct_index = i
                options.append(opt[1:].strip())
            else:
                options.append(opt)
                
        if correct_index != -1:
            questions.append({
                "question": question_text,
                "options": options,
                "correct_index": correct_index
            })

    return questions

def get_shuffled_questions(filepath):
    questions = load_questions(filepath)
    # Shuffle options internally
    for q in questions:
        opts = q['options']
        correct_str = opts[q['correct_index']]
        
        # shuffle options indices
        shuffled_indices = list(range(len(opts)))
        random.shuffle(shuffled_indices)
        
        new_opts = [opts[i] for i in shuffled_indices]
        new_correct_index = new_opts.index(correct_str)
        
        q['options'] = new_opts
        q['correct_index'] = new_correct_index

    # Shuffle the questions themselves
    random.shuffle(questions)
    return questions
