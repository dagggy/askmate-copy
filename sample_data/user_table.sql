ALTER TABLE IF EXISTS ONLY public.user DROP CONSTRAINT IF EXISTS pk_user_id CASCADE;

DROP TABLE IF EXISTS public.user;
CREATE TABLE public.user (
    user_id serial NOT NULL,
    username_link text,
    registration_date timestamp without time zone,
    questions_number integer,
    answers_number integer,
    comments_number integer,
    user_reputation integer
);

INSERT INTO public.user VALUES (1, NULL, '2017-04-28 08:29:00', 2, 7, 1, 5);
